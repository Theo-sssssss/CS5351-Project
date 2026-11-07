import hashlib
import hmac
import tempfile
import unittest
from pathlib import Path

from evoagent_v3.app import verify_webhook_signature
from evoagent_v3.llm import LLMResult
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


class FakeLLM:
    model = "fake-model"

    def __init__(self):
        self.roles = []

    def complete_json(self, system_prompt, user_prompt):
        if "Lead reviewer" in system_prompt:
            role = "lead"
            value = {"summary": "refund change", "security_focus": ["authorization"], "correctness_focus": ["state"], "files": ["orders.py"]}
        elif "Security reviewer" in system_prompt:
            role = "security"
            value = {"findings": [dict(FINDING)]}
        elif "Correctness and Reliability" in system_prompt:
            role = "correctness"
            value = {"findings": []}
        elif "Lead producing" in system_prompt:
            role = "lead_synthesis"
            value = {"summary": "There is a refund-authorization risk.", "findings": [dict(FINDING)]}
        elif "Critic" in system_prompt:
            role = "critic"
            value = {"summary": "supported", "findings": [dict(FINDING)], "rejected_candidates": []}
        else:
            role = "baseline"
            value = {"summary": "baseline", "findings": [dict(FINDING)]}
        self.roles.append(role)
        return LLMResult(value, 10, 5)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.temp.name) / "test.db"))
        self.llm = FakeLLM()
        self.engine = WorkflowEngine(self.llm, self.store)

    def tearDown(self):
        self.temp.cleanup()

    def task(self, mode):
        return self.store.create_task("owner/repo", 1, "test", mode)

    def test_baseline_uses_one_call(self):
        task_id = self.task("baseline")
        report, metrics = self.engine.review(task_id, "owner/repo", 1, DIFF, "baseline")
        self.assertEqual(["baseline"], self.llm.roles)
        self.assertEqual(1, metrics["call_count"])
        self.assertEqual(1, len(report["findings"]))

    def test_collaborative_uses_five_roles(self):
        task_id = self.task("collaborative")
        report, metrics = self.engine.review(task_id, "owner/repo", 1, DIFF, "collaborative")
        self.assertEqual(5, metrics["call_count"])
        self.assertEqual({"lead", "security", "correctness", "critic", "lead_synthesis"}, set(self.llm.roles))
        self.assertEqual("collaborative", report["mode"])

    def test_collaborative_records_five_traces(self):
        task_id = self.task("collaborative")
        self.engine.review(task_id, "owner/repo", 1, DIFF, "collaborative")
        self.assertEqual(5, len(self.store.role_runs(task_id)))

    def test_collaborative_preserves_worker_and_critic_attribution(self):
        task_id = self.task("collaborative")
        report, _ = self.engine.review(task_id, "owner/repo", 1, DIFF, "collaborative")
        self.assertEqual(["critic", "security"], report["findings"][0]["reported_by"])

    def test_tokens_are_summed(self):
        task_id = self.task("collaborative")
        _, metrics = self.engine.review(task_id, "owner/repo", 1, DIFF, "collaborative")
        self.assertEqual(50, metrics["input_tokens"])
        self.assertEqual(25, metrics["output_tokens"])

    def test_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            self.engine.review(self.task("baseline"), "owner/repo", 1, DIFF, "autonomous")


class WebhookTests(unittest.TestCase):
    def test_valid_signature(self):
        body = b'{"action":"opened"}'
        signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook_signature("secret", body, signature))

    def test_invalid_signature(self):
        self.assertFalse(verify_webhook_signature("secret", b"body", "sha256=bad"))

    def test_missing_secret_is_invalid(self):
        self.assertFalse(verify_webhook_signature("", b"body", "sha256=bad"))


if __name__ == "__main__":
    unittest.main()
