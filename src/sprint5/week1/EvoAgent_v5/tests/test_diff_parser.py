# Diff 解析测试：检查新增行在新文件中的位置，防止删除行影响新行号。

import unittest

from evoagent.diff_parser import parse_unified_diff


DIFF = """diff --git a/app.py b/app.py
index 123..456 100644
--- a/app.py
+++ b/app.py
@@ -2,3 +2,4 @@ def run():
 keep = True
-old = 1
+new = 2
+eval(user_input)
 tail = 3
"""


# 集中验证本模块的正常行为、错误路径及数据边界。
class DiffParserTests(unittest.TestCase):
    # 验证新增行号按新文件推进，删除行不占用新文件行号。
    def test_parses_added_line_numbers(self):
        parsed = parse_unified_diff(DIFF)
        self.assertEqual(["app.py"], parsed.files)
        self.assertEqual([(3, "new = 2"), (4, "eval(user_input)")], [(x.line, x.content) for x in parsed.added_lines])


if __name__ == "__main__":
    unittest.main()

