# 本地规则测试：确保风险检测仅针对新增代码行。

import unittest

from evoagent.diff_parser import parse_unified_diff
from evoagent.reviewer import LocalRuleReviewer


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


if __name__ == "__main__":
    unittest.main()

