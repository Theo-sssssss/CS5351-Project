# 提示词学习验证测试：使用固定数据集检验反馈能否改善仓库隔离的保留集结果。

import ast
import os
import tempfile
import unittest

from evoagent.evolution_proof import (
    generate_prompt_evolution_cases,
    run_prompt_evolution_proof,
    write_jsonl,
)
from evoagent.diff_parser import parse_unified_diff
from evoagent.patching import apply_file_patch, parse_unified_patch
from evoagent.review_rules import ContextRuleReviewer
from evoagent.reviewer import LocalRuleReviewer


# 集中验证本模块的正常行为、错误路径及数据边界。
class PromptEvolutionProofTests(unittest.TestCase):
    def test_contextual_fixtures_apply_and_preserve_exact_findings(self):
        for case in generate_prompt_evolution_cases():
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
                for added in parsed.added_lines:
                    self.assertEqual(
                        added.content,
                        case["after_files"][added.path].splitlines()[added.line - 1],
                    )
                actual = [
                    finding
                    for reviewer in (LocalRuleReviewer(), ContextRuleReviewer())
                    for finding in reviewer.review(case["diff"], parsed)
                ]
                self.assertCountEqual(
                    [(item["rule_id"], item["path"], item["start_line"], item["severity"])
                     for item in case["expected_findings"]],
                    [(item.rule_id, item.path, item.line, item.severity.value)
                     for item in actual],
                )

    # 验证反馈演进的效果能在不同仓库的保留集上复现。
    def test_feedback_evolution_improves_repository_disjoint_holdout(self):
        cases = generate_prompt_evolution_cases()
        self.assertEqual(130, len(cases))
        validation_repositories = {
            case["repository"] for case in cases if case["split"] == "validation"
        }
        holdout_repositories = {
            case["repository"] for case in cases if case["split"] == "holdout"
        }
        self.assertEqual(8, len(validation_repositories))
        self.assertEqual(2, len(holdout_repositories))
        self.assertFalse(validation_repositories & holdout_repositories)

        with tempfile.TemporaryDirectory() as directory:
            dataset_path = os.path.join(directory, "cases.jsonl")
            database_path = os.path.join(directory, "proof.db")
            write_jsonl(cases, dataset_path)
            report = run_prompt_evolution_proof(dataset_path, database_path)

        self.assertEqual("activated", report["evolution_run"]["decision"])
        self.assertEqual(32, report["feedback"]["missed_findings"])
        self.assertGreater(
            report["validation"]["candidate"]["f1"],
            report["validation"]["baseline"]["f1"],
        )
        self.assertGreater(
            report["holdout"]["candidate"]["f1"],
            report["holdout"]["baseline"]["f1"],
        )
        self.assertTrue(report["release_gate"]["quantitative_passed"])
        self.assertFalse(report["release_gate"]["production_activation_allowed"])


if __name__ == "__main__":
    unittest.main()
