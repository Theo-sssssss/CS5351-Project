# 端到端评测测试：覆盖一对一匹配、CWE 身份规范和数据集指纹。

import ast
import os
import tempfile
import unittest

from evoagent.evaluation_experiments import load_controlled_pr_cases
from evoagent.evolution import RegressionEvaluator
from evoagent.evaluation_harness import (
    dataset_fingerprint,
    load_jsonl,
    one_to_one_match,
)
from evoagent.diff_parser import parse_unified_diff
from evoagent.models import Finding, Severity
from evoagent.patching import apply_file_patch, parse_unified_patch


# 集中验证本模块的正常行为、错误路径及数据边界。
class EndToEndEvaluationTests(unittest.TestCase):
    def test_contextual_dataset_patches_apply_and_labels_cover_added_lines(self):
        for case in load_controlled_pr_cases():
            with self.subTest(case=case["id"]):
                paths = list(case["after_files"])
                patches = parse_unified_patch(case["diff"], paths)
                for patch in patches:
                    before = case["before_files"][patch.path]
                    after = case["after_files"][patch.path]
                    ast.parse(before, filename=patch.path)
                    ast.parse(after, filename=patch.path)
                    self.assertEqual(after, apply_file_patch(before, patch))

                parsed = parse_unified_diff(case["diff"])
                added = {(item.path, item.line) for item in parsed.added_lines}
                for finding in case["expected_findings"]:
                    self.assertIn(
                        (finding["path"], finding["start_line"]), added
                    )
                    self.assertEqual(finding["start_line"], finding["end_line"])

    # 验证固定数据集的样本数量和仓库级划分符合实验约定。
    def test_generated_dataset_has_repository_level_split_and_expected_counts(self):
        cases = load_controlled_pr_cases()
        self.assertEqual(100, len(cases))
        self.assertEqual(40, sum(bool(item["expected_findings"]) for item in cases))
        self.assertEqual(60, sum(not item["expected_findings"] for item in cases))
        validation_repos = {
            item["repository"] for item in cases if item["split"] == "validation"
        }
        holdout_repos = {
            item["repository"] for item in cases if item["split"] == "holdout"
        }
        self.assertEqual(8, len(validation_repos))
        self.assertEqual(2, len(holdout_repos))
        self.assertFalse(validation_repos & holdout_repos)
        self.assertEqual(
            {"offline-fixture"},
            {item["source"]["kind"] for item in cases},
        )

    # 验证重复预测只能匹配一次，不会增加真实命中数。
    def test_one_to_one_matching_counts_duplicate_prediction_once(self):
        expected = [{
            "path": "src/a.py", "start_line": 10, "end_line": 12,
            "cwe": "CWE-95", "severity": "critical",
        }]
        predicted = [
            Finding(
                "SEC-EVAL", Severity.CRITICAL, "a", "long enough explanation",
                "src/a.py", line, "eval(x)", "replace eval safely",
                "add malicious input test", 0.9,
            )
            for line in (10, 11)
        ]
        matches = one_to_one_match(expected, predicted)
        self.assertEqual(1, len(matches))

    # 验证有明确 CWE 时按标准身份匹配，不依赖任意模型规则名。
    def test_one_to_one_matching_uses_explicit_cwe_not_random_rule_id(self):
        expected = [{
            "path": "src/a.py", "start_line": 10, "end_line": 10,
            "cwe": "CWE-95", "severity": "critical",
        }]
        predicted = [Finding(
            "MODEL-GENERATED-LABEL", Severity.CRITICAL, "a",
            "long enough explanation", "src/a.py", 10, "eval(x)",
            "replace eval safely", "add malicious input test", 0.9,
            cwe="CWE-95",
        )]
        self.assertEqual(1, len(one_to_one_match(expected, predicted)))

    # 验证未知规则且未提供 CWE 的预测无法冒充已知问题。
    def test_one_to_one_matching_rejects_unknown_rule_without_cwe(self):
        expected = [{
            "path": "src/a.py", "start_line": 10, "end_line": 10,
            "cwe": "CWE-95", "severity": "critical",
        }]
        predicted = [Finding(
            "MODEL-GENERATED-LABEL", Severity.CRITICAL, "a",
            "long enough explanation", "src/a.py", 10, "eval(x)",
            "replace eval safely", "add malicious input test", 0.9,
        )]
        self.assertEqual([], one_to_one_match(expected, predicted))

    # 验证模型自定义标签在 CWE 正确时仍可被回放评测匹配。
    def test_prompt_replay_accepts_model_label_when_cwe_is_canonical(self):
        case = {
            "name": "canonical-cwe",
            "diff": "--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+eval(data)\n",
            "expected": [{
                "path": "a.py", "line": 1, "rule_id": "SEC-EVAL",
                "min_severity": "high",
            }],
        }

        # 本组测试的可控替身，用预设响应隔离外部依赖。
        class Reviewer:
            name = "test"

            # 按当前测试场景生成预设问题或触发异常，供断言验证调用方的处理逻辑。
            def review(self, _diff, parsed):
                line = parsed.added_lines[0]
                return [Finding(
                    "MODEL-LABEL", Severity.CRITICAL, "x", "x",
                    line.path, line.line, line.content, "fix", "test", 0.9,
                    cwe="CWE-95",
                )]

        report = RegressionEvaluator(lambda _prompt: Reviewer()).run("p", [case])
        self.assertEqual(1, report["case_results"][0]["tp"])

    # 验证数据集写出再读回后内容指纹保持一致。
    def test_dataset_round_trip_has_stable_fingerprint(self):
        cases = load_controlled_pr_cases()
        handle, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(handle)
        try:
            import json
            with open(path, "w", encoding="utf-8") as output:
                for case in cases:
                    output.write(json.dumps(case, ensure_ascii=False) + "\n")
            loaded = load_jsonl(path)
            self.assertEqual(dataset_fingerprint(cases), dataset_fingerprint(loaded))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
