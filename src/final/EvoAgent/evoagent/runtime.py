# 工作流运行时：按节点执行并维护步数、超时、重试、取消和持久化检查点。
# 工具注册表负责在调用处理函数前校验参数契约。

"""EvoAgent's dependency-free durable workflow runtime and tool registry.

The runtime deliberately separates orchestration from agent behaviour:

* ``AgentRuntime`` executes named nodes with budgets, retry policy, cancellation
  checks and application-owned checkpoints.
Tool-using model loops live in ``agentic_core.BoundedRole``. Persistence remains
in the application store so a worker restart does not depend on a
framework-owned checkpoint format.
"""
from contextlib import nullcontext
from dataclasses import dataclass, field
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


# 表示执行预算耗尽，调用方应结束当前执行而非继续重试。
class RuntimeBudgetExceeded(RuntimeError):
    """The configured step or wall-clock budget was exhausted."""


# 表示任务收到取消请求，用于区分主动取消与业务失败。
class RuntimeCancelled(RuntimeError):
    """The owning task requested cancellation."""


# 表示工具名或参数不符合已注册契约。
class ToolProtocolError(RuntimeError):
    """A tool request does not match the registered tool contract."""


# 绑定工具名称、描述、参数 Schema 与内部处理函数。
@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]

    # 仅导出工具契约，不把内部处理函数传给模型。
    def catalog_entry(self) -> Dict[str, Any]:
        return {
            "name": self.name, "description": self.description,
            "parameters": self.parameters,
        }


# 模型可调用工具的显式目录，同时承担调用前参数校验。
class ToolRegistry:
    """Explicit tool catalog with JSON-schema-like argument validation."""

    # 建立空工具目录，并通过统一注册检查加载初始工具集合。
    def __init__(self, tools: Iterable[AgentTool] = ()):
        self._tools: Dict[str, AgentTool] = {}
        for tool in tools:
            self.register(tool)

    # 要求工具名非空且唯一，防止工具处理函数被静默覆盖。
    def register(self, tool: AgentTool) -> None:
        if not tool.name or tool.name in self._tools:
            raise ValueError("tool names must be non-empty and unique")
        self._tools[tool.name] = tool

    # 按名称排序返回工具列表，使目录顺序稳定。
    def names(self) -> List[str]:
        return sorted(self._tools)

    # 按稳定顺序生成模型可见的工具名称、描述和参数 Schema。
    def catalog(self) -> List[Dict[str, Any]]:
        return [self._tools[name].catalog_entry() for name in self.names()]

    # 先查找已注册工具并校验参数，再调用其处理函数。
    def invoke(self, name: str, arguments: Dict[str, Any]) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolProtocolError("unknown agent tool: %s" % name)
        self._validate(tool.parameters, arguments)
        return tool.handler(**arguments)

    # 根据工具参数 Schema 检查必填项、未知字段、类型及数值范围。
    @staticmethod
    def _validate(schema: Dict[str, Any], arguments: Dict[str, Any]) -> None:
        if not isinstance(arguments, dict):
            raise ToolProtocolError("tool arguments must be an object")
        properties = dict(schema.get("properties") or {})
        required = set(schema.get("required") or [])
        missing = required.difference(arguments)
        if missing:
            raise ToolProtocolError(
                "missing required tool arguments: %s" % ", ".join(sorted(missing))
            )
        if schema.get("additionalProperties", False) is False:
            unknown = set(arguments).difference(properties)
            if unknown:
                raise ToolProtocolError(
                    "unknown tool arguments: %s" % ", ".join(sorted(unknown))
                )
        # Python 的 bool 是 int 的子类；下面对数值类型额外排除 bool，保持 JSON 类型语义。
        expected_types = {
            "string": str, "integer": int, "number": (int, float),
            "boolean": bool, "object": dict, "array": list,
        }
        for key, value in arguments.items():
            spec = properties.get(key) or {}
            expected = expected_types.get(spec.get("type"))
            if expected and (not isinstance(value, expected) or (
                spec.get("type") in {"integer", "number"} and isinstance(value, bool)
            )):
                raise ToolProtocolError(
                    "tool argument %s must be %s" % (key, spec.get("type"))
                )
            if isinstance(value, (int, float)):
                if "minimum" in spec and value < spec["minimum"]:
                    raise ToolProtocolError("tool argument %s is below minimum" % key)
                if "maximum" in spec and value > spec["maximum"]:
                    raise ToolProtocolError("tool argument %s exceeds maximum" % key)


# 工作流节点定义，包含处理函数、重试覆盖值与是否保存检查点。
@dataclass(frozen=True)
class RuntimeNode:
    name: str
    handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    retries: Optional[int] = None
    checkpoint: bool = True


# 运行时事件数据，记录节点、步数、尝试次数及附加详情。
@dataclass(frozen=True)
class RuntimeEvent:
    kind: str
    node: str
    step: int
    attempt: int = 0
    detail: Dict[str, Any] = field(default_factory=dict)


# 顺序执行可恢复节点图，统一处理预算、取消、事件和重试。
class AgentRuntime:
    """Execute a bounded node graph without a third-party orchestration engine."""

    # 验证步数、耗时和重试参数的合法性，再保存节点执行策略。
    def __init__(
        self, max_steps: int = 8, timeout_seconds: int = 120,
        node_retries: int = 0,
    ):
        if max_steps < 1:
            raise ValueError("runtime max_steps must be at least 1")
        if timeout_seconds < 1:
            raise ValueError("runtime timeout_seconds must be at least 1")
        if node_retries < 0:
            raise ValueError("runtime node_retries cannot be negative")
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds
        self.node_retries = node_retries

    # 按节点顺序执行；已完成检查点直接恢复输出，失败节点按策略重试并累计预算。
    def execute(
        self, initial_state: Dict[str, Any], nodes: Iterable[RuntimeNode],
        task_id: str = "", checkpoint_store=None,
        cancel_check: Optional[Callable[[], bool]] = None,
        event_sink: Optional[Callable[[RuntimeEvent], None]] = None,
        span_factory: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
        non_retryable: Tuple[type, ...] = (ValueError, RuntimeCancelled, RuntimeBudgetExceeded),
    ) -> Dict[str, Any]:
        state = dict(initial_state)
        started = time.monotonic()
        steps = 0
        checkpoints = (
            checkpoint_store.load_checkpoints(task_id)
            if checkpoint_store is not None and task_id else {}
        )

        # 把运行事件发送给调用方，统一附带节点、步数和尝试次数。
        def emit(kind: str, node: str, attempt: int = 0, **detail) -> None:
            if event_sink:
                event_sink(RuntimeEvent(kind, node, steps, attempt, detail))

        # 在每次节点尝试前检查取消、步数和总耗时预算，超限立即停止。
        def guard(node: str) -> None:
            if cancel_check and cancel_check():
                emit("cancelled", node)
                raise RuntimeCancelled("Task was cancelled")
            if steps >= self.max_steps or time.monotonic() - started > self.timeout_seconds:
                emit("budget_exhausted", node)
                raise RuntimeBudgetExceeded("task execution budget exceeded")

        for node in nodes:
            cached = checkpoints.get(node.name) if node.checkpoint else None
            # 已完成节点只恢复它保存的输出；跳过处理函数，避免重试时重复产生副作用。
            if cached and cached.get("status") == "completed":
                output = dict(cached.get("state") or {})
                state.update(output)
                emit("checkpoint_restored", node.name, int(cached.get("attempt", 0)))
                continue

            retries = self.node_retries if node.retries is None else node.retries
            previous_attempt = int((cached or {}).get("attempt", 0))
            last_error: Optional[Exception] = None
            # retries 表示额外重试次数，因此总尝试次数要再加首次执行。
            for offset in range(1, retries + 2):
                guard(node.name)
                # 每次实际尝试都消耗一步预算，重试也不能绕过全局上限。
                steps += 1
                attempt = previous_attempt + offset
                emit("node_started", node.name, attempt)
                try:
                    attrs = {
                        "task_id": task_id, "node": node.name,
                        "attempt": attempt, "runtime_step": steps,
                    }
                    context = (
                        span_factory("runtime.%s" % node.name, attrs)
                        if span_factory else nullcontext()
                    )
                    with context:
                        output = node.handler(state) or {}
                    if not isinstance(output, dict):
                        raise TypeError("runtime node %s must return a dict" % node.name)
                    state.update(output)
                    if checkpoint_store is not None and task_id and node.checkpoint:
                        checkpoint_store.save_checkpoint(
                            task_id, node.name, output, "completed", attempt
                        )
                    emit("node_completed", node.name, attempt, output_keys=sorted(output))
                    last_error = None
                    break
                # 参数错误、主动取消和预算耗尽通常无法靠重试恢复，直接交给上层结束任务。
                except non_retryable:
                    raise
                except Exception as exc:
                    last_error = exc
                    if checkpoint_store is not None and task_id and node.checkpoint:
                        checkpoint_store.save_checkpoint(
                            task_id, node.name, {}, "failed", attempt, str(exc)
                        )
                    emit(
                        "node_failed", node.name, attempt,
                        error=str(exc)[:1000], will_retry=offset <= retries,
                    )
            if last_error is not None:
                raise last_error
        return state
