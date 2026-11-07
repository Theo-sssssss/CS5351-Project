import json
import tempfile
import unittest
from pathlib import Path

from evoagent_v3.diff_parser import parse_unified_diff
from evoagent_v3.llm import LLMResult
from evoagent_v3.repository_tools import RepositoryToolSuite
from evoagent_v3.runtime import (
    AgentRuntime,
    AgentTool,
    RuntimeBudget,
    RuntimeBudgetExceeded,
    RuntimeCancelled,
    RuntimeLedger,
    ToolProtocolError,
    ToolRegistry,
)
from evoagent_v3.store import Store
from evoagent_v3.workflow import WorkflowEngine


DIFF = """diff --git a/orders.py b/orders.py
--- a/orders.py
+++ b/orders.py
@@ -1,2 +1,3 @@
 def refund(order, actor):
+    gateway.refund(order.payment_id)
     return True
"""

FINDING = {
    "rule_id": "authz.refund",
    "category": "security",
    "severity": "high",
    "title": "Refund lacks authorization",
    "explanation": "The added refund call has no visible ownership check.",
    "path": "orders.py",
    "line": 2,
    "evidence": "gateway.refund(order.payment_id)",
    "fix": "Authorize the actor before refunding.",
    "test": "Reject a refund from another user.",
    "confidence": 0.91,
}


class RepositoryToolTests(unittest.TestCase):
    def setUp(self):
        self.suite = RepositoryToolSuite(parse_unified_diff(DIFF))

    def test_lists_and_reads_only_added_lines(self):
        self.assertEqual([{"path": "orders.py", "added_lines": 1}], self.suite.list_changed_files()["files"])
        self.assertEqual(2, self.suite.get_added_lines("b/orders.py")["lines"][0]["line"])

    def test_search_and_context_are_bounded_to_diff(self):
        self.assertEqual(1, len(self.suite.search_added_code("REFUND")["matches"]))
        self.assertTrue(self.suite.get_diff_context("orders.py", 2)["lines"][0]["target"])
        with self.assertRaises(ValueError):
            self.suite.get_added_lines("secrets.env")


class SequenceLLM:
    model = "fake-model"

    def __init__(self, values):
        self.values = list(values)
        self.calls = 0

    def complete_json(self, _system_prompt, _user_prompt):
        self.calls += 1
        return LLMResult(self.values.pop(0), 7, 3)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.temp.name) / "runtime.db"))
        self.task_id = self.store.create_task("owner/repo", 1, "test", "agentic")
        self.registry = ToolRegistry()
        self.registry.register(
            AgentTool(
                "echo",
                "Return one value.",
                lambda value: {"value": value},
                frozenset({"lead"}),
                required=frozenset({"value"}),
            )
        )

    def tearDown(self):
        self.temp.cleanup()

    def runtime(self, llm, budget=None):
        return AgentRuntime(llm, self.registry, self.store, RuntimeLedger(budget or RuntimeBudget()))

    def test_tool_then_final_records_trace_and_checkpoint(self):
        llm = SequenceLLM(
            [
                {"action": "tool", "tool": "echo", "arguments": {"value": "ok"}},
                {"action": "final", "result": {"summary": "done"}},
            ]
        )
        result = self.runtime(llm).run_role(
            self.task_id, "agentic:lead", "lead", 1, "inspect", {}, {"echo"}
        )
        self.assertEqual("done", result["summary"])
        self.assertEqual("SUCCESS", self.store.tool_events(self.task_id)[0]["state"])
        self.assertEqual("COMPLETED", self.store.get_checkpoint(self.task_id, "agentic:lead")["state"])

    def test_nested_tool_and_final_envelopes(self):
        llm = SequenceLLM(
            [
                {"tool": {"action": "tool", "tool": "echo", "arguments": {"value": "ok"}}},
                {"tool": None, "final": {"action": "final", "result": {"summary": "done"}}},
            ]
        )
        result = self.runtime(llm).run_role(
            self.task_id, "agentic:lead", "lead", 1, "inspect", {}, {"echo"}
        )
        self.assertEqual("done", result["summary"])
        self.assertEqual("SUCCESS", self.store.tool_events(self.task_id)[0]["state"])

    def test_completed_checkpoint_skips_model(self):
        self.store.save_checkpoint(
            self.task_id, "agentic:lead", "COMPLETED", {"result": {"summary": "cached"}}
        )
        llm = SequenceLLM([])
        result = self.runtime(llm).run_role(
            self.task_id, "agentic:lead", "lead", 1, "inspect", {}, {"echo"}
        )
        self.assertEqual("cached", result["summary"])
        self.assertEqual(0, llm.calls)

    def test_permissions_and_argument_schema_are_enforced(self):
        with self.assertRaises(ToolProtocolError):
            self.registry.invoke("critic", {"echo"}, "echo", {"value": "x"})
        with self.assertRaises(ToolProtocolError):
            self.registry.invoke("lead", {"echo"}, "echo", {"unexpected": "x"})

    def test_cancellation_stops_before_model_call(self):
        self.assertTrue(self.store.request_cancel(self.task_id))
        llm = SequenceLLM([{"action": "final", "result": {}}])
        with self.assertRaises(RuntimeCancelled):
            self.runtime(llm).run_role(
                self.task_id, "agentic:lead", "lead", 1, "inspect", {}, {"echo"}
            )
        self.assertEqual(0, llm.calls)

    def test_role_step_budget_is_hard_limit(self):
        llm = SequenceLLM([{"action": "tool", "tool": "echo", "arguments": {"value": "x"}}])
        with self.assertRaises(RuntimeBudgetExceeded):
            self.runtime(llm, RuntimeBudget(max_steps_per_role=1)).run_role(
                self.task_id, "agentic:lead", "lead", 1, "inspect", {}, {"echo"}
            )


class AgenticFakeLLM:
    model = "fake-agentic-model"

    def complete_json(self, system_prompt, user_prompt):
        if "bounded review agent" not in system_prompt:
            return LLMResult({"summary": "final", "findings": [dict(FINDING)]}, 10, 5)
        payload = json.loads(user_prompt)
        mission = payload["mission"].lower()
        observed = bool(payload["observations"])
        if "bounded plan" in mission:
            value = (
                {"action": "final", "result": {"summary": "plan", "security_focus": ["authorization"], "correctness_focus": ["state"], "files": ["orders.py"]}}
                if observed
                else {"action": "tool", "tool": "list_changed_files", "arguments": {}}
            )
        elif "authentication" in mission:
            value = (
                {"action": "final", "result": {"findings": [dict(FINDING)]}}
                if observed
                else {"action": "tool", "tool": "get_diff_context", "arguments": {"path": "orders.py", "line": 2}}
            )
        elif "state transitions" in mission:
            value = (
                {"action": "final", "result": {"findings": []}}
                if observed
                else {"action": "tool", "tool": "search_added_code", "arguments": {"query": "refund"}}
            )
        else:
            value = (
                {"action": "final", "result": {"summary": "supported", "findings": [dict(FINDING)], "rejected_candidates": []}}
                if observed
                else {"action": "tool", "tool": "get_diff_context", "arguments": {"path": "orders.py", "line": 2}}
            )
        return LLMResult(value, 10, 5)


class AgenticWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.temp.name) / "workflow.db"))

    def tearDown(self):
        self.temp.cleanup()

    def test_agentic_mode_uses_tools_budgets_and_checkpoints(self):
        task_id = self.store.create_task("owner/repo", 1, "test", "agentic")
        engine = WorkflowEngine(AgenticFakeLLM(), self.store, RuntimeBudget(max_calls=12))
        report, metrics = engine.review(task_id, "owner/repo", 1, DIFF, "agentic")
        self.assertEqual("agentic", report["mode"])
        self.assertEqual(1, len(report["findings"]))
        self.assertEqual(4, metrics["tool_call_count"])
        self.assertEqual(9, metrics["call_count"])
        self.assertEqual(5, len(self.store.checkpoints(task_id)))


if __name__ == "__main__":
    unittest.main()
