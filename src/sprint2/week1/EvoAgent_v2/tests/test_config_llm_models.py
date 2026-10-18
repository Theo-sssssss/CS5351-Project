import unittest

from evoagent_v2.config import Settings, verified_ssl_context
from evoagent_v2.llm import parse_json_object
from evoagent_v2.models import normalize_finding, report_risk


class ConfigurationTests(unittest.TestCase):
    def test_preserves_exact_chat_endpoint(self):
        url = "https://example.test/v1/chat/completions"
        self.assertEqual(url, Settings.normalize_chat_url(url))

    def test_builds_chat_endpoint_from_base(self):
        self.assertEqual(
            "https://example.test/v1/chat/completions",
            Settings.normalize_chat_url("https://example.test/v1/"),
        )

    def test_empty_base_stays_empty(self):
        self.assertEqual("", Settings.normalize_chat_url(""))

    def test_verified_ssl_context_has_ca_certificates(self):
        self.assertGreater(len(verified_ssl_context().get_ca_certs()), 0)


class JsonAndModelTests(unittest.TestCase):
    def test_parses_fenced_json(self):
        self.assertEqual({"findings": []}, parse_json_object('```json\n{"findings": []}\n```'))

    def test_extracts_json_from_surrounding_text(self):
        self.assertEqual("ok", parse_json_object('Result: {"summary":"ok"} done')["summary"])

    def test_rejects_array_root(self):
        with self.assertRaises(ValueError):
            parse_json_object("[]")

    def test_normalizes_invalid_values(self):
        item = normalize_finding({"severity": "urgent", "line": "bad", "confidence": 4})
        self.assertEqual("medium", item["severity"])
        self.assertEqual(0, item["line"])
        self.assertEqual(1.0, item["confidence"])

    def test_report_risk_uses_highest_severity(self):
        self.assertEqual("critical", report_risk([{"severity": "low"}, {"severity": "critical"}]))


if __name__ == "__main__":
    unittest.main()
