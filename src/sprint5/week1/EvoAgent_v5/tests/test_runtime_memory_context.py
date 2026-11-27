# 运行时与记忆测试：覆盖检查点、工具契约、记忆生命周期及任务和角色隔离。

import os
import tempfile
import unittest
import json

from evoagent.agentic_core import BoundedRole
from evoagent.context_manager import ContextManager
from evoagent.memory import MemoryManager
from evoagent.runtime import (
    AgentRuntime, AgentTool, RuntimeNode, ToolProtocolError, ToolRegistry,
)
from evoagent.store import TaskStore, utc_now
from evoagent.telemetry import ExecutionLedger


# 集中验证本模块的正常行为、错误路径及数据边界。
class RuntimeMemoryTests(unittest.TestCase):
    # 为每个测试创建独立夹具和临时资源，避免前一个用例的状态影响当前断言。
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.store = TaskStore(self.path)

    # 释放本用例创建的资源并清理临时数据，保持测试之间互不干扰。
    def tearDown(self):
        os.unlink(self.path)

    # 验证已完成节点直接恢复检查点输出，不再次调用处理函数。
    def test_runtime_restores_completed_node_checkpoints(self):
        self.store.create("runtime-task", "org/repo", 1, {})
        runtime = AgentRuntime(max_steps=4, timeout_seconds=5)
        calls = []
        nodes = [
            RuntimeNode("plan", lambda _state: calls.append("plan") or {"value": 2}),
            RuntimeNode(
                "execute",
                lambda state: calls.append("execute") or {"result": state["value"] * 3},
            ),
        ]

        first = runtime.execute({}, nodes, "runtime-task", self.store)
        second = runtime.execute({}, nodes, "runtime-task", self.store)

        self.assertEqual(6, first["result"])
        self.assertEqual(6, second["result"])
        self.assertEqual(["plan", "execute"], calls)

    # 验证参数契约不满足时，在工具处理函数执行前拒绝请求。
    def test_tool_registry_validates_arguments_before_invocation(self):
        calls = []
        registry = ToolRegistry([AgentTool(
            "lookup", "Lookup one key.",
            {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"], "additionalProperties": False,
            },
            lambda key: calls.append(key) or "value:%s" % key,
        )])

        with self.assertRaisesRegex(ToolProtocolError, "unknown tool arguments"):
            registry.invoke("lookup", {"key": 7, "unexpected": True})

        self.assertEqual([], calls)
        self.assertEqual("value:x", registry.invoke("lookup", {"key": "x"}))
        self.assertEqual(["x"], calls)

    # 验证记忆召回同时限制租户和仓库范围。
    def test_memory_recall_is_repository_and_tenant_isolated(self):
        memory = MemoryManager(self.store, recall_limit=5)
        memory.remember(
            "tenant-a", "org/repo", "semantic", "review_feedback",
            "SEC-EVAL was a confirmed missed issue in authentication code",
            importance=0.9,
        )
        memory.remember(
            "tenant-b", "org/repo", "semantic", "review_feedback",
            "REL-DEBUG-PRINT was accepted", importance=0.9,
        )

        recalled = memory.recall(
            "tenant-a", "org/repo", "authentication SEC-EVAL security"
        )

        self.assertEqual(1, len(recalled))
        self.assertIn("SEC-EVAL", recalled[0]["content"])
        self.assertEqual([], memory.recall("tenant-a", "org/other", "SEC-EVAL"))

    # 验证召回前清理过期记忆，不再返回失效信息。
    def test_memory_recall_purges_expired_records(self):
        self.store.save_agent_memory({
            "id": "expired-memory", "tenant_id": "tenant-a",
            "repository": "org/repo", "task_id": "old-task", "agent": "agent",
            "scope": "working", "kind": "observation", "content": "expired content",
            "keywords": ["expired"], "metadata": {}, "importance": 0.5,
            "created_at": utc_now(), "expires_at": "2000-01-01T00:00:00+00:00",
        })

        MemoryManager(self.store).recall("tenant-a", "org/repo", "expired")

        self.assertEqual([], self.store.list_agent_memories(
            "tenant-a", "org/repo", ("working",), 10
        ))

    # 验证工具观察可写入工作记忆，并在下一步模型调用中读取。
    def test_tool_observation_is_written_and_visible_to_next_agent_step(self):
        memory = MemoryManager(self.store, recall_limit=8)
        seen = []

        # 本组测试的可控替身，用预设响应隔离外部依赖。
        class ToolThenFinalClient:
            provider = "fake"
            model = "fake"

            # 按角色和输入上下文返回确定性 JSON，并记录测试需要核对的调用信息。
            def complete_json(_self, _role, _prompt, user, ledger=None, max_tokens=None):
                managed = json.loads(user)
                task = json.loads(managed["task"])
                seen.append(task.get("working_memory"))
                if ledger:
                    ledger.record_model("security", "fake", "fake", {
                        "prompt_tokens": 10, "completion_tokens": 3,
                    }, 1)
                if len(seen) == 1:
                    return {"action": "tool", "tool": "lookup", "arguments": {"key": "auth"}}
                return {"action": "final", "findings": []}

        # 读取本测试任务的工作记忆，供模拟角色下一步调用使用。
        def supplier():
            values = memory.recall_working("tenant-a", "org/repo", "task")
            return ContextManager.format_memories(values) if values else None

        # 保存模拟工具观察，用于验证写入到下一步召回的链路。
        def sink(agent, observation):
            memory.remember_observation(
                "tenant-a", "org/repo", "task", agent, observation,
            )

        role = BoundedRole(
            "security", "Use facts.", ToolThenFinalClient(), 1000, 10,
            context_manager=ContextManager(), working_memory_supplier=supplier,
            observation_sink=sink,
        )
        registry = ToolRegistry([AgentTool(
            "lookup", "Lookup a fact.", {
                "type": "object", "properties": {"key": {"type": "string"}},
                "required": ["key"], "additionalProperties": False,
            }, lambda key: {"evidence_id": "lookup:%s" % key, "output": {"value": "allowed"}},
        )])

        role.run(json.dumps({"phase": "worker"}), registry, ExecutionLedger("agentic"))

        self.assertIsNone(seen[0])
        self.assertEqual("tool_observation", seen[1]["items"][0]["kind"])
        self.assertIn("lookup:auth", seen[1]["items"][0]["content"])

    # 验证任务结束时释放短期观察，同时保留归档摘要。
    def test_task_consolidation_releases_working_memory_but_keeps_episode(self):
        memory = MemoryManager(self.store)
        memory.remember_observation("tenant-a", "org/repo", "task", "security", {
            "step": 1, "tool": "symbol", "ok": True,
            "result": {"evidence_id": "symbol:auth", "output": {"callers": ["api"]}},
        })

        memory.consolidate_task("tenant-a", "org/repo", "task", {"accepted_findings": []})

        self.assertEqual([], memory.recall_working("tenant-a", "org/repo", "task"))
        archived = memory.recall("tenant-a", "org/repo", "completed task")
        self.assertEqual("task_summary", archived[0]["kind"])

    # 验证同任务中不同角色的工作记忆互相隔离。
    def test_working_memory_is_isolated_by_agent_role(self):
        memory = MemoryManager(self.store)
        memory.remember_observation("tenant-a", "org/repo", "task", "security", {
            "step": 1, "tool": "lookup", "ok": True,
            "result": {"evidence_id": "security:auth", "output": "security fact"},
        })
        memory.remember_observation("tenant-a", "org/repo", "task", "correctness-reliability", {
            "step": 1, "tool": "lookup", "ok": True,
            "result": {"evidence_id": "correctness:auth", "output": "correctness fact"},
        })

        security = memory.recall_working(
            "tenant-a", "org/repo", "task", agent="security",
        )
        critic = memory.recall_working(
            "tenant-a", "org/repo", "task", agent="critic",
        )

        self.assertEqual(1, len(security))
        self.assertIn("security:auth", security[0]["content"])
        self.assertEqual([], critic)


if __name__ == "__main__":
    unittest.main()
