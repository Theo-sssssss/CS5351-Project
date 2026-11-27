# 服务集成测试：从创建任务到报告与反馈，核对正常审查调用路径及输入限制。

import os
import tempfile
import unittest

from evoagent.config import Settings
from evoagent.service import ReviewService
from agentic_fake import enable_agentic_service


# 集中验证本模块的正常行为、错误路径及数据边界。
class ServiceTests(unittest.TestCase):
    # 为每个测试创建独立夹具和临时资源，避免前一个用例的状态影响当前断言。
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.settings = Settings(
            host="127.0.0.1", port=8080, db_path=self.path, max_diff_bytes=10000,
            max_steps=8, timeout_seconds=10, llm_base_url="", llm_api_key="", llm_model="",
            github_webhook_secret="", github_token="", auto_post_review=False,
        )

    # 释放本用例创建的资源并清理临时数据，保持测试之间互不干扰。
    def tearDown(self):
        os.unlink(self.path)

    # 验证同步审查生成完整报告，普通任务按约定完成 5 次角色模型调用。
    def test_end_to_end_review(self):
        diff = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+eval(data)\n"
        service = enable_agentic_service(ReviewService(self.settings))
        self.assertEqual([], service.reviewer.scanners)
        result = service.create_review("org/repo", diff, 1)
        task = service.store.get(result["task_id"])
        service.queue.close()
        self.assertEqual("SUCCESS", result["state"])
        self.assertEqual("SEC-EVAL", result["report"]["findings"][0]["rule_id"])
        self.assertEqual("agentic", result["report"]["run_mode"]["effective"])
        self.assertEqual(
            ["lead", "security", "correctness-reliability", "critic"],
            result["report"]["collaboration"]["roles"],
        )
        self.assertEqual(5, result["report"]["execution"]["llm_calls"])
        self.assertEqual("normal", result["report"]["collaboration"]["risk_level"])
        role_calls = {}
        for call in result["report"]["execution"]["model_call_log"]:
            role_calls[call["role"]] = role_calls.get(call["role"], 0) + 1
        self.assertEqual({
            "lead": 2, "security": 1,
            "correctness-reliability": 1, "critic": 1,
        }, role_calls)
        self.assertEqual(0, result["report"]["collaboration"]["revision_rounds"])
        self.assertGreater(result["report"]["execution"]["tool_calls"], 0)
        self.assertEqual([], task["collaboration"])

    # 验证超出字节数限制的 Diff 在创建审查前被拒绝。
    def test_rejects_large_diff(self):
        service = enable_agentic_service(ReviewService(self.settings))
        with self.assertRaises(ValueError):
            service.create_review("org/repo", "x" * 10001)

    # 验证已完成审查的反馈能保存，并按任务和租户查询。
    def test_completed_review_feedback_is_persisted_and_listed_per_task(self):
        diff = "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+eval(data)\n"
        service = enable_agentic_service(ReviewService(self.settings))
        result = service.create_review(
            "org/repo", diff, 1, enabled_skills=["security-review"],
        )
        task_id = result["task_id"]

        feedback = service.record_feedback(
            task_id, "false_positive", result["report"]["findings"][0], "不是实际风险",
            skill_name="security-review",
        )

        self.assertEqual({
            "recorded": True, "category": "false_positive", "skill_name": "security-review",
        }, feedback)
        cases = service.store.list_task_failure_cases(task_id, "default")
        self.assertEqual(1, len(cases))
        self.assertEqual("false_positive", cases[0]["category"])
        self.assertEqual("security-review", cases[0]["skill_name"])
        self.assertEqual("SEC-EVAL", cases[0]["payload"]["finding"]["rule_id"])
        service.queue.close()


if __name__ == "__main__":
    unittest.main()
