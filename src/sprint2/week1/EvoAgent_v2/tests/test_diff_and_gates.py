import unittest

from evoagent_v2.diff_parser import normalize_path, parse_unified_diff
from evoagent_v2.gates import validate_findings


DIFF = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -10,2 +10,4 @@
 keep = True
+password = request.args["password"]
+run(password)
 old = 1
diff --git a/new.py b/new.py
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+TOKEN = "demo"
+print(TOKEN)
"""


def finding(**updates):
    value = {
        "rule_id": "input.untrusted",
        "category": "security",
        "severity": "high",
        "title": "Untrusted password",
        "explanation": "Untrusted input reaches a call.",
        "path": "app.py",
        "line": 11,
        "evidence": 'password = request.args["password"]',
        "fix": "Validate it.",
        "test": "Add a hostile-input test.",
        "confidence": 0.9,
    }
    value.update(updates)
    return value


class DiffParserTests(unittest.TestCase):
    def test_parses_files(self):
        self.assertEqual({"app.py", "new.py"}, parse_unified_diff(DIFF).files)

    def test_parses_added_line_numbers(self):
        parsed = parse_unified_diff(DIFF)
        self.assertEqual('password = request.args["password"]', parsed.lines_for("app.py")[11])
        self.assertEqual("run(password)", parsed.lines_for("app.py")[12])

    def test_parses_new_file(self):
        self.assertEqual('TOKEN = "demo"', parse_unified_diff(DIFF).lines_for("new.py")[1])

    def test_normalizes_git_prefix(self):
        self.assertEqual("src/a.py", normalize_path("b/src/a.py"))


class FindingGateTests(unittest.TestCase):
    def setUp(self):
        self.parsed = parse_unified_diff(DIFF)

    def test_accepts_evidence_backed_finding(self):
        result = validate_findings([finding()], self.parsed)
        self.assertEqual(1, len(result.accepted))
        self.assertFalse(result.rejected)

    def test_rejects_unknown_path(self):
        result = validate_findings([finding(path="missing.py")], self.parsed)
        self.assertEqual("path_not_in_diff", result.rejected[0]["reason"])

    def test_rejects_context_line(self):
        result = validate_findings([finding(line=10, evidence="keep = True")], self.parsed)
        self.assertEqual("line_not_added", result.rejected[0]["reason"])

    def test_rejects_wrong_evidence(self):
        result = validate_findings([finding(evidence="eval(user_input)")], self.parsed)
        self.assertEqual("evidence_not_on_added_line", result.rejected[0]["reason"])

    def test_repairs_line_when_evidence_is_unique(self):
        result = validate_findings([finding(line=999)], self.parsed)
        self.assertEqual(11, result.accepted[0]["line"])

    def test_deduplicates_and_merges_reporters(self):
        one = finding(reported_by=["security"])
        two = finding(reported_by=["critic"], confidence=0.95)
        result = validate_findings([one, two], self.parsed)
        self.assertEqual(1, len(result.accepted))
        self.assertEqual(["critic", "security"], result.accepted[0]["reported_by"])
        self.assertEqual("duplicate", result.rejected[0]["reason"])


if __name__ == "__main__":
    unittest.main()
