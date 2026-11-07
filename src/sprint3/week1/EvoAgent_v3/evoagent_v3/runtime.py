from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


class RuntimeBudgetExceeded(RuntimeError):
    pass


class RuntimeCancelled(RuntimeError):
    pass


class ToolProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    handler: Callable[..., dict]
    allowed_roles: frozenset[str]
    required: frozenset[str] = frozenset()
    optional: frozenset[str] = frozenset()


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def descriptions(self, role: str, allowed: set[str]) -> list[dict]:
        return [
            {"name": tool.name, "description": tool.description, "required": sorted(tool.required), "optional": sorted(tool.optional)}
            for name, tool in sorted(self._tools.items())
            if name in allowed and role in tool.allowed_roles
        ]

    def invoke(self, role: str, allowed: set[str], name: str, arguments: dict) -> dict:
        if name not in allowed:
            raise ToolProtocolError(f"tool is not allowed for this role: {name}")
        tool = self._tools.get(name)
        if not tool or role not in tool.allowed_roles:
            raise ToolProtocolError(f"tool is unavailable for this role: {name}")
        if not isinstance(arguments, dict):
            raise ToolProtocolError("tool arguments must be an object")
        keys = set(arguments)
        missing = tool.required - keys
        unknown = keys - tool.required - tool.optional
        if missing:
            raise ToolProtocolError("missing tool arguments: " + ", ".join(sorted(missing)))
        if unknown:
            raise ToolProtocolError("unknown tool arguments: " + ", ".join(sorted(unknown)))
        return tool.handler(**arguments)


@dataclass(frozen=True)
class RuntimeBudget:
    max_steps_per_role: int = 4
    max_calls: int = 18
    max_tokens: int = 30000
    timeout_seconds: int = 240


@dataclass
class RuntimeLedger:
    budget: RuntimeBudget
    started: float = field(default_factory=time.monotonic)
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    model_latency_ms: int = 0
    tool_calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def before_call(self, cancelled: Callable[[], bool]) -> None:
        with self._lock:
            if cancelled():
                raise RuntimeCancelled("Task cancellation requested")
            if time.monotonic() - self.started > self.budget.timeout_seconds:
                raise RuntimeBudgetExceeded("Agent runtime time budget exceeded")
            if self.calls >= self.budget.max_calls:
                raise RuntimeBudgetExceeded("Agent runtime model-call budget exceeded")
            self.calls += 1

    def record_model(self, input_tokens: int, output_tokens: int, latency_ms: int) -> None:
        with self._lock:
            self.input_tokens += int(input_tokens)
            self.output_tokens += int(output_tokens)
            self.model_latency_ms += int(latency_ms)
            if self.input_tokens + self.output_tokens > self.budget.max_tokens:
                raise RuntimeBudgetExceeded("Agent runtime token budget exceeded")

    def record_tool(self) -> None:
        with self._lock:
            self.tool_calls += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "call_count": self.calls,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "model_latency_ms": self.model_latency_ms,
                "tool_call_count": self.tool_calls,
                "elapsed_ms": round((time.monotonic() - self.started) * 1000),
                "budget": {
                    "max_steps_per_role": self.budget.max_steps_per_role,
                    "max_calls": self.budget.max_calls,
                    "max_tokens": self.budget.max_tokens,
                    "timeout_seconds": self.budget.timeout_seconds,
                },
            }


class AgentRuntime:
    def __init__(self, llm, registry: ToolRegistry, store, ledger: RuntimeLedger):
        self.llm = llm
        self.registry = registry
        self.store = store
        self.ledger = ledger

    @staticmethod
    def _decode_action(value: dict) -> tuple[str, dict]:
        """Accept equivalent JSON envelopes without relaxing tool permissions."""
        if not isinstance(value, dict):
            raise ToolProtocolError("agent response must be an object")
        if value.get("action") == "tool":
            return "tool", value
        if value.get("action") == "final":
            return "final", value
        tool = value.get("tool")
        if isinstance(tool, str) and tool:
            return "tool", {"tool": tool, "arguments": value.get("arguments", {})}
        if isinstance(tool, dict):
            return "tool", tool
        final = value.get("final")
        if isinstance(final, dict):
            return "final", final
        if "findings" in value or "summary" in value:
            return "final", {"result": value}
        raise ToolProtocolError("agent action must be tool or final")

    def run_role(
        self,
        task_id: str,
        node: str,
        role: str,
        phase: int,
        mission: str,
        context: dict,
        allowed_tools: set[str],
    ) -> dict:
        checkpoint = self.store.get_checkpoint(task_id, node) if self.store else None
        if checkpoint and checkpoint["state"] == "COMPLETED":
            return checkpoint["data"]["result"]
        observations = []
        start_step = 0
        if checkpoint and checkpoint["state"] == "RUNNING":
            observations = checkpoint["data"].get("observations") or []
            start_step = int(checkpoint["data"].get("next_step") or 0)
        tools = self.registry.descriptions(role, allowed_tools)
        for step in range(start_step, self.ledger.budget.max_steps_per_role):
            self.ledger.before_call(lambda: bool(self.store and self.store.is_cancel_requested(task_id)))
            user = json.dumps(
                {
                    "mission": mission,
                    "context": context,
                    "available_tools": tools,
                    "observations": observations,
                    "step": step + 1,
                    "max_steps": self.ledger.budget.max_steps_per_role,
                    "response_contract": {
                        "tool": {"action": "tool", "tool": "tool_name", "arguments": {}},
                        "final": {"action": "final", "result": {}},
                    },
                },
                ensure_ascii=False,
            )
            digest = hashlib.sha256(user.encode("utf-8")).hexdigest()
            run_id = self.store.start_role(task_id, role, phase, self.llm.model, digest) if self.store else 0
            started = time.monotonic()
            try:
                response = self.llm.complete_json(
                    "You are a bounded review agent. Use only the listed read-only tools. Return exactly one response-contract JSON object. Never request a tool outside your role permission.",
                    user,
                )
                latency_ms = max(0, round((time.monotonic() - started) * 1000))
                if self.store:
                    self.store.finish_role(run_id, response.value, latency_ms, response.input_tokens, response.output_tokens)
                self.ledger.record_model(response.input_tokens, response.output_tokens, latency_ms)
            except Exception as exc:
                latency_ms = max(0, round((time.monotonic() - started) * 1000))
                if self.store:
                    self.store.fail_role(run_id, str(exc), latency_ms)
                raise
            action, action_value = self._decode_action(response.value)
            if action == "final":
                result = action_value.get("result", action_value)
                if not isinstance(result, dict):
                    raise ToolProtocolError("final result must be an object")
                if self.store:
                    self.store.save_checkpoint(task_id, node, "COMPLETED", {"result": result, "steps": step + 1})
                return result
            tool_name = str(action_value.get("tool") or "")
            arguments = action_value.get("arguments", {})
            tool_started = time.monotonic()
            try:
                output = self.registry.invoke(role, allowed_tools, tool_name, arguments)
                tool_latency = max(0, round((time.monotonic() - tool_started) * 1000))
                if self.store:
                    self.store.record_tool_event(task_id, role, step + 1, tool_name, arguments, output, "SUCCESS", tool_latency)
            except Exception as exc:
                tool_latency = max(0, round((time.monotonic() - tool_started) * 1000))
                output = {"error": str(exc)}
                if self.store:
                    self.store.record_tool_event(task_id, role, step + 1, tool_name, arguments, output, "FAILED", tool_latency)
            self.ledger.record_tool()
            observations.append({"tool": tool_name, "arguments": arguments, "output": output})
            if self.store:
                self.store.save_checkpoint(
                    task_id,
                    node,
                    "RUNNING",
                    {"next_step": step + 1, "observations": observations},
                )
        raise RuntimeBudgetExceeded(f"Agent role step budget exceeded: {role}")
