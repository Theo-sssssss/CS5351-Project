# 本地规则测试：确保风险检测仅针对新增代码行。

import unittest
from difflib import unified_diff

from evoagent.diff_parser import parse_unified_diff
from evoagent.reviewer import LocalRuleReviewer, ZERO_DIVISOR_GUARD_RULE


# 集中验证本模块的正常行为、错误路径及数据边界。
class LocalReviewerTests(unittest.TestCase):
    # 验证本地规则只报告新增代码风险，不报告已删除代码。
    def test_detects_security_findings_only_on_added_lines(self):
        diff = """--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
-eval(old_input)
+password = "super-secret"
+eval(user_input)
 safe = True
"""
        findings = LocalRuleReviewer().review(diff, parse_unified_diff(diff))
        self.assertEqual({"SEC-EVAL", "SEC-HARDCODED-SECRET"}, {item.rule_id for item in findings})
        self.assertTrue(all(item.line in {1, 2} for item in findings))

    def test_reports_only_replacements_that_remove_the_divisors_guard(self):
        cases = (
            ("return total / count if count else 0", "return total / count", True),
            ("return total // count if count != 0 else 0", "return total // count", True),
            ("return 0 if count == 0 else total / count", "return total / count", True),
            ("return total / count if enabled else 0", "return total / count", False),
            ("return total / count if count else 0", "return total / count if count != 0 else 0", False),
            ("return total / count if count else 0", "return total / divisor", False),
            ("return total / count if count else 0", "return total / count if count else 0.0", False),
        )
        for old, new, expected in cases:
            with self.subTest(old=old, new=new):
                diff = f"--- a/calc.py\n+++ b/calc.py\n@@ -5 +6 @@\n-    {old}\n+    {new}\n"
                findings = LocalRuleReviewer().review(diff, parse_unified_diff(diff))
                self.assertEqual(int(expected), len(findings))
                if expected:
                    finding, = findings
                    self.assertEqual((ZERO_DIVISOR_GUARD_RULE, "calc.py", 6, new),
                                     (finding.rule_id, finding.path, finding.line, finding.evidence))
                    self.assertEqual(5, finding.evidence_refs[0]["old_line"])

    def test_leaves_equivalent_range_and_floor_checks_alone(self):
        before = (
            "def apply_discount(price, percent):\n"
            "    if percent < 0 or percent > 100:\n"
            "        raise ValueError('invalid percent')\n"
            "    total = round(price * (1 - percent / 100), 2)\n"
            "    return max(0.0, total)\n"
        )
        after = (
            "def apply_discount(price, percent):\n"
            "    if not 0 <= percent <= 100:\n"
            "        raise ValueError('invalid percent')\n"
            "    total = round(price * (1 - percent / 100), 2)\n"
            "    return 0.0 if total < 0 else total\n"
        )
        diff = "".join(unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                   fromfile="a/discount.py", tofile="b/discount.py"))
        self.assertEqual([], LocalRuleReviewer().review(diff, parse_unified_diff(diff)))


if __name__ == "__main__":
    unittest.main()

