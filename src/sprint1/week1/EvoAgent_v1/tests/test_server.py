import unittest

from server import normalize_report, parse_json_object


class PromptReviewTests(unittest.TestCase):
    def test_json_in_fence_is_accepted(self):
        value = parse_json_object('```json\n{"risk":"high","findings":[]}\n```')
        self.assertEqual("high", value["risk"])

    def test_report_is_normalized_and_sorted(self):
        report = normalize_report({"summary":"ok","findings":[
            {"severity":"low","title":"minor","path":"b.py","line":2},
            {"severity":"critical","title":"important","path":"a.py","line":1},
        ]}, "owner/repo", 1)
        self.assertEqual("critical", report["risk"])
        self.assertEqual("important", report["findings"][0]["title"])


if __name__ == "__main__":
    unittest.main()
