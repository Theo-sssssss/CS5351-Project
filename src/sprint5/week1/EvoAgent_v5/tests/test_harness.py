# 工作流测试：验证成功任务的状态轨迹，以及无效 Diff 的失败持久化。

import os
import tempfile
import unittest

from evoagent.harness import ReviewHarness
from evoagent.reviewer import LocalRuleReviewer
from evoagent.store import TaskStore


# 集中验证本模块的正常行为、错误路径及数据边界。
class HarnessTests(unittest.TestCase):
    # 为每个测试创建独立夹具和临时资源，避免前一个用例的状态影响当前断言。
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.store = TaskStore(self.path)

    # 释放本用例创建的资源并清理临时数据，保持测试之间互不干扰。
    def tearDown(self):
        os.unlink(self.path)

    # 验证成功审查按状态机顺序保存完整轨迹与报告。
    def test_successful_state_flow_is_persisted(self):
        task_id = "test-task"
        self.store.create(task_id, "demo/repo", 7, {"source": "test"})
        diff = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+eval(value)\n"
        report = ReviewHarness(self.store, LocalRuleReviewer()).run(task_id, "demo/repo", 7, diff)
        task = self.store.get(task_id)
        self.assertEqual("SUCCESS", task["state"])
        self.assertEqual(["PLANNING", "EXECUTING", "REVIEWING", "SUCCESS"], [x["state"] for x in task["trace"]])
        self.assertEqual("high", report.risk)

    # 验证无效 Diff 触发失败，并将原因保存到任务记录。
    def test_invalid_diff_is_recorded_as_failure(self):
        task_id = "bad-task"
        self.store.create(task_id, "demo/repo", None, {"source": "test"})
        with self.assertRaises(ValueError):
            ReviewHarness(self.store, LocalRuleReviewer()).run(task_id, "demo/repo", None, "not a diff")
        self.assertEqual("FAILED", self.store.get(task_id)["state"])


if __name__ == "__main__":
    unittest.main()

