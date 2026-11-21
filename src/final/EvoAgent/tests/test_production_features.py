# 生产能力测试：覆盖认证与租户隔离、Webhook 幂等、队列死信、恢复和灰度回滚。

import os
import sqlite3
import tempfile
import time
import unittest

from evoagent.auth import AuthManager
from evoagent.harness import ReviewHarness
from evoagent.reviewer import LocalRuleReviewer
from evoagent.rollout import ReleaseManager
from evoagent.service import ReviewService
from evoagent.store import TaskStore
from evoagent.task_queue import TaskQueue
from evoagent.verifier import RepairVerifier


DIFF = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+eval(data)\n"


# 集中验证本模块的正常行为、错误路径及数据边界。
class ProductionFeatureTests(unittest.TestCase):
    # 为每个测试创建独立夹具和临时资源，避免前一个用例的状态影响当前断言。
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.store = TaskStore(self.path)

    # 释放本用例创建的资源并清理临时数据，保持测试之间互不干扰。
    def tearDown(self):
        os.unlink(self.path)

    # 验证登录、角色权限与租户任务隔离共同生效。
    def test_login_rbac_and_tenant_task_isolation(self):
        auth = AuthManager(
            self.store, "a" * 32, bootstrap_username="alice",
            bootstrap_password="correct-horse", default_tenant_id="tenant-a",
        )
        token = auth.login("alice", "correct-horse")["access_token"]
        principal = auth.authenticate("Bearer " + token)
        self.assertTrue(principal.can("manage"))
        self.store.create("a", "org/a", 1, {}, "tenant-a")
        self.store.create("b", "org/b", 2, {}, "tenant-b")
        self.assertIsNotNone(self.store.get("a", principal.tenant_id))
        self.assertIsNone(self.store.get("b", principal.tenant_id))
        self.assertEqual(["a"], [item["id"] for item in self.store.list_tasks(10, "tenant-a")])

    # 验证同一 delivery ID 幂等，且不能绑定不同请求体。
    def test_webhook_delivery_is_idempotent_and_payload_bound(self):
        self.assertTrue(self.store.claim_webhook("delivery-1", "t", "pull_request", "aaa"))
        self.assertFalse(self.store.claim_webhook("delivery-1", "t", "pull_request", "aaa"))
        with self.assertRaisesRegex(ValueError, "different payload"):
            self.store.claim_webhook("delivery-1", "t", "pull_request", "bbb")

    # 验证案例列表不会返回其他租户的反馈。
    def test_failure_cases_are_filtered_by_tenant(self):
        self.store.create("a", "org/a", 1, {}, "tenant-a")
        self.store.create("b", "org/b", 2, {}, "tenant-b")
        self.store.record_failure_case("a", "false_positive", {"note": "a"})
        self.store.record_failure_case("b", "missed_issue", {"note": "b"})

        cases = self.store.list_failure_cases(tenant_id="tenant-a")

        self.assertEqual(["a"], [item["task_id"] for item in cases])

    # 验证旧数据库升级后，历史未归属反馈只进入通用 llm-review 队列。
    def test_legacy_failure_cases_migrate_to_llm_review_scope(self):
        handle, legacy_path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        try:
            with sqlite3.connect(legacy_path) as conn:
                conn.execute(
                    "CREATE TABLE failure_cases (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "task_id TEXT NOT NULL,category TEXT NOT NULL,payload_json TEXT NOT NULL,"
                    "resolved INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL)"
                )
                conn.execute(
                    "INSERT INTO failure_cases(task_id,category,payload_json,created_at) "
                    "VALUES ('legacy','missed_issue','{}','2026-01-01T00:00:00+00:00')"
                )
            conn.close()

            migrated = TaskStore(legacy_path)

            self.assertEqual(
                ["legacy"],
                [item["task_id"] for item in migrated.list_failure_cases(
                    skill_name="llm-review",
                )],
            )
            self.assertEqual([], migrated.list_failure_cases(skill_name="security-review"))
        finally:
            os.unlink(legacy_path)

    # 验证失败工作流从最近完成节点后继续，而非重跑整个任务。
    def test_failed_graph_resumes_after_last_completed_checkpoint(self):
        # 本组测试的可控替身，用预设响应隔离外部依赖。
        class BrokenReviewer:
            name = "broken"

            # 按当前测试场景生成预设问题或触发异常，供断言验证调用方的处理逻辑。
            def review(self, _diff, _parsed):
                raise RuntimeError("temporary provider failure")

        self.store.create("task", "org/repo", 1, {})
        with self.assertRaises(RuntimeError):
            ReviewHarness(
                self.store, BrokenReviewer(), node_retries=0
            ).run("task", "org/repo", 1, DIFF)
        checkpoints = self.store.load_checkpoints("task")
        self.assertEqual("completed", checkpoints["planning"]["status"])
        self.assertEqual("failed", checkpoints["executing"]["status"])

        report = ReviewHarness(
            self.store, LocalRuleReviewer(), node_retries=0
        ).resume("task", "org/repo", 1, DIFF)
        self.assertEqual("high", report.risk)
        planning_events = [
            item for item in self.store.get("task")["trace"] if item["state"] == "PLANNING"
        ]
        self.assertEqual(1, len(planning_events))

    # 验证不可重试错误直接移入死信队列。
    def test_queue_moves_terminal_failure_to_dlq(self):
        # 主动抛出终止性异常，用于验证死信处理行为。
        def broken(_payload):
            raise RuntimeError("boom")

        queue = TaskQueue(broken, workers=1, max_attempts=1)
        queue.submit({"task_id": "dead"})
        for _ in range(100):
            if queue.dead_letters():
                break
            time.sleep(.01)
        letters = queue.dead_letters()
        queue.close()
        self.assertEqual("dead", letters[0]["message_id"])
        self.assertIn("boom", letters[0]["error"])

    # 验证死信回调会结束待处理任务，避免任务状态悬挂。
    def test_dead_letter_marks_pending_task_failed(self):
        self.store.create("dead", "org/repo", 1, {}, "tenant")
        service = ReviewService.__new__(ReviewService)
        service.store = self.store

        service._on_dead_letter({"task_id": "dead", "tenant_id": "tenant"}, "boom")

        task = self.store.get("dead", "tenant")
        self.assertEqual("FAILED", task["state"])
        self.assertEqual("boom", task["error"])

    # 验证灰度分桶稳定，错误超预算时触发回滚。
    def test_canary_assignment_and_error_budget_rollback(self):
        release = ReleaseManager(self.store)
        release.configure("tenant", "skill", {
            "stable_version": 1, "candidate_version": 2,
            "canary_percent": 100, "shadow_percent": 100,
            "min_samples": 2, "max_error_rate": .25,
        })
        self.assertEqual("canary", release.assignment("tenant", "skill", "task")["lane"])
        release.observe("tenant", "skill", True)
        result = release.observe("tenant", "skill", False)
        self.assertEqual("rolled_back", result["status"])
        self.assertTrue(self.store.list_alerts("tenant"))

    # 验证修复后的 Python 语法错误会阻止放行。
    def test_repair_verifier_blocks_invalid_python(self):
        result = RepairVerifier().verify_contents({"app.py": "def broken(:\n"})
        self.assertFalse(result["passed"])
        self.assertEqual("compile:app.py", result["checks"][0]["name"])


if __name__ == "__main__":
    unittest.main()
