# 多 Agent 评测测试：核对共享规则集、实际角色拓扑和生产声明的数据要求。

import json
import unittest

from evoagent.diff_parser import parse_unified_diff
from evoagent.review_rules import ContextRuleReviewer
from evoagent.evaluation_v2 import (
    FairAblationSuite,
    ProductArmReviewer,
    product_reviewer_factories,
)
from evoagent.reviewer import LocalRuleReviewer


DIFF = (
    "--- a/app.py\n"
    "+++ b/app.py\n"
    "@@ -0,0 +1 @@\n"
    "+value = open(base / user_path)\n"
)


# 本组测试的可控替身，用预设响应隔离外部依赖。
class FakeClient:
    provider = "fake"
    model = "fake-model"

    # 按角色和输入上下文返回确定性 JSON，并记录测试需要核对的调用信息。
    def complete_json(self, role, _system, user, ledger=None, max_tokens=None):
        if ledger:
            ledger.record_model(
                role, self.provider, self.model,
                {"prompt_tokens": 10, "completion_tokens": 5}, 1,
            )
        if role == "lead":
            managed = json.loads(user)
            task = json.loads(managed["task"])
            if task["phase"] == "delegate":
                return {
                    "action": "final",
                    "delegations": [
                        {
                            "assignment_id": "security-1", "worker": "security",
                            "objective": "Review security",
                        },
                        {
                            "assignment_id": "reliability-1",
                            "worker": "correctness-reliability",
                            "objective": "Review correctness",
                        },
                    ],
                }
            if task["phase"] == "assess-workers":
                return {
                    "action": "final", "revision_requests": [],
                    "critic_objective": "Blindly verify every candidate.",
                }
            if task["phase"] == "finalize":
                return {
                    "action": "final",
                    "accepted_finding_indices": list(
                        range(len(task["candidate_findings"]))
                    ),
                    "confidence_adjustments": [],
                }
            raise AssertionError(task["phase"])
        if role in {"security", "correctness-reliability"}:
            return {"action": "final", "findings": []}
        if role == "critic":
            managed = json.loads(user)
            task = json.loads(managed["task"])
            return {
                "action": "final",
                "decisions": [
                    {
                        "finding_index": index,
                        "accepted": True,
                        "objections": [],
                        "confidence_adjustment": 0.0,
                    }
                    for index, _item in enumerate(task["candidates"])
                ],
            }
        raise AssertionError(role)


# 集中验证本模块的正常行为、错误路径及数据边界。
class AgenticEvaluationTests(unittest.TestCase):
    # 验证实验组共享同一组 14 条规则，且调用日志符合各组真实角色拓扑。
    def test_agentic_arms_share_exactly_fourteen_rules_and_real_role_topologies(self):
        self.assertEqual(14, len(LocalRuleReviewer.RULES) + len(ContextRuleReviewer.RULES))
        expected_calls = {
            "multi-llm-no-critic": {
                "lead": 2, "security": 1,
                "correctness-reliability": 1,
            },
            "full-agentic": {
                "lead": 2, "security": 1,
                "correctness-reliability": 1, "critic": 1,
            },
        }
        parsed = parse_unified_diff(DIFF)
        for arm, calls in expected_calls.items():
            reviewer = ProductArmReviewer(arm, FakeClient(), 4096, 40)
            findings = reviewer.review(DIFF, parsed)
            self.assertEqual(["SEC-PATH-TRAVERSAL"], [item.rule_id for item in findings])
            actual = {}
            for item in reviewer.evaluation_execution()["model_call_log"]:
                actual[item["role"]] = actual.get(item["role"], 0) + 1
            self.assertEqual(calls, actual)
            self.assertEqual(14, reviewer.evaluation_config()["deterministic_rules"])

    # 验证非生产数据允许调试，但不能据此给出生产效果结论。
    def test_non_production_data_can_debug_but_cannot_prove_claims(self):
        cases = []
        for index, split in enumerate(("train", "validation", "holdout"), 1):
            cases.append({
                "id": "case-%d" % index,
                "repository": "repo-%d" % index,
                "pull_request": index,
                "split": split,
                "source": {"kind": "offline-fixture"},
                "diff": DIFF,
                "expected_findings": [{
                    "path": "app.py", "start_line": 1, "end_line": 1,
                    "rule_id": "SEC-PATH-TRAVERSAL", "cwe": "CWE-22",
                    "severity": "high", "should_comment": True,
                }],
            })
        suite = FairAblationSuite(
            product_reviewer_factories(FakeClient(), 40),
            "fake-model", 4096, require_production_ready=False,
            bootstrap_iterations=200,
        )
        report = suite.run(cases)
        self.assertFalse(report["dataset"]["ready"])
        self.assertFalse(report["critic_gate"]["passed"])
        self.assertEqual(
            {
                "lead": 6, "security": 3,
                "correctness-reliability": 3, "critic": 3,
            },
            report["arms"]["full-agentic"]["execution"]["model_role_calls"],
        )


if __name__ == "__main__":
    unittest.main()
