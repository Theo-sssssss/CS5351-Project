import unittest

from evoagent.agentic_core import _parse_findings
from evoagent.diff_parser import parse_unified_diff
from evoagent.finding_identity import (
    canonical_cwe, normalize_worker_identity, worker_rule_catalog,
)


DIFF = "--- a/app.py\n+++ b/app.py\n@@ -0,0 +1 @@\n+dangerous_call(data)\n"


class FindingIdentityTests(unittest.TestCase):
    def test_program_mapping_overrides_model_supplied_cwe(self):
        self.assertEqual("CWE-95", canonical_cwe("SEC-EVAL", "CWE-999"))

    def test_worker_catalog_is_role_scoped(self):
        security = {item["rule_id"] for item in worker_rule_catalog("security")}
        correctness = {
            item["rule_id"] for item in worker_rule_catalog("correctness-reliability")
        }
        self.assertIn("SEC-EVAL", security)
        self.assertNotIn("SEC-EVAL", correctness)
        self.assertIn("REL-ERROR-HANDLING", correctness)

    def test_skill_declared_rule_is_allowed_without_model_cwe(self):
        self.assertEqual(
            ("SEC-DANGEROUS-CALL", "", True),
            normalize_worker_identity(
                "SEC-DANGEROUS-CALL", "CWE-999", "security",
                ["SEC-DANGEROUS-CALL"],
            ),
        )

    def test_invented_rule_is_downgraded_and_self_confidence_is_ignored(self):
        parsed = parse_unified_diff(DIFF)
        result = {"findings": [{
            "rule_id": "SEC-INVENTED-BY-MODEL", "cwe": "CWE-999",
            "severity": "medium", "title": "Candidate",
            "explanation": "Needs classification.", "path": "app.py", "line": 1,
            "evidence": "dangerous_call(data)", "fix": "Use a safe API.",
            "test": "Add a regression test.", "confidence": 1.0,
        }]}

        finding = _parse_findings(result, parsed, "security")[0]

        self.assertEqual("UNCLASSIFIED-SECURITY", finding.rule_id)
        self.assertIsNone(finding.cwe)
        self.assertEqual(0.5, finding.confidence)


if __name__ == "__main__":
    unittest.main()
