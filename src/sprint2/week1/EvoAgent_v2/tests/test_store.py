import tempfile
import unittest
from pathlib import Path

from evoagent_v2.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.temp.name) / "test.db"))

    def tearDown(self):
        self.temp.cleanup()

    def test_task_round_trip(self):
        task_id = self.store.create_task("owner/repo", 3, "test", "baseline")
        self.store.set_running(task_id)
        self.store.set_success(task_id, {"findings": []}, {"call_count": 1})
        task = self.store.get(task_id)
        self.assertEqual("SUCCESS", task["state"])
        self.assertEqual(1, task["metrics"]["call_count"])

    def test_delivery_failure_preserves_success_report(self):
        task_id = self.store.create_task("owner/repo", 3, "test", "baseline")
        self.store.set_success(task_id, {"summary": "kept"}, {"call_count": 1})
        self.store.set_delivery(task_id, "FAILED", "comment denied")
        task = self.store.get(task_id)
        self.assertEqual("SUCCESS", task["state"])
        self.assertEqual("kept", task["report"]["summary"])
        self.assertEqual("FAILED", task["delivery_state"])

    def test_role_trace_round_trip(self):
        task_id = self.store.create_task("owner/repo", 3, "test", "collaborative")
        run_id = self.store.start_role(task_id, "lead", 1, "model", "abc")
        self.store.finish_role(run_id, {"summary": "plan"}, 17, 10, 5)
        run = self.store.get(task_id)["role_runs"][0]
        self.assertEqual("SUCCESS", run["state"])
        self.assertEqual(15, run["input_tokens"] + run["output_tokens"])

    def test_delivery_ids_are_idempotent(self):
        self.assertTrue(self.store.remember_delivery("delivery-1"))
        self.assertFalse(self.store.remember_delivery("delivery-1"))

    def test_recovers_interrupted_tasks(self):
        task_id = self.store.create_task("owner/repo", 3, "test", "baseline")
        self.store.set_running(task_id)
        self.assertEqual(1, self.store.recover_interrupted())
        self.assertEqual("FAILED", self.store.get(task_id)["state"])


if __name__ == "__main__":
    unittest.main()
