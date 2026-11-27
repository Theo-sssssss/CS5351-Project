import json
import os
import tempfile
import time
import unittest
from dataclasses import replace

from agentic_fake import FakeAgenticClient, enable_agentic_service
from evoagent.batch_review import BatchReview, ReviewConflict
from evoagent.config import Settings
from evoagent.evolution import EvolutionEngine
from evoagent.models import Finding, Severity
from evoagent.python_guard_rules import INPUT_RANGE_GUARD_RULE, ZERO_FLOOR_RULE
from evoagent.review_batches import parse_changes, plan_batches, token_bound
from evoagent.reviewer import ZERO_DIVISOR_GUARD_RULE
from evoagent.service import ReviewService


DIFF = "--- a/a.py\n+++ b/a.py\n@@ -5 +5 @@\n-old_value\n+new_value\n"


class ReviewBatchTests(unittest.TestCase):
    def test_large_lines_and_deletions_are_preserved(self):
        old = "old_" * 1000
        new = "ä中x" * 2000
        diff = (f"--- a/previous name.txt\n+++ b/new name.txt\n@@ -10 +28 @@\n-{old}\n+{new}\n"
                "--- a/removed.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-removed content\n"
                "diff --git a/picture.png b/picture.png\nBinary files a/picture.png and b/picture.png differ\n")
        batches, excluded = plan_batches(diff, 410)
        changed = [item for batch in batches for item in parse_changes(batch["diff"])[0]]
        self.assertTrue(all(token_bound(batch["diff"]) <= 410 for batch in batches))
        self.assertEqual(old, "".join(item.text for item in changed if item.side == "-" and item.line == 10))
        self.assertEqual(new, "".join(item.text for item in changed if item.side == "+" and item.line == 28))
        self.assertEqual(["removed content"], [item.text for item in changed if item.old_path == "removed.txt"])
        self.assertEqual([{"path": "picture.png", "kind": "binary"}], excluded)

    def test_inconsistent_hunk_cannot_be_marked_covered(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            plan_batches("--- a/a\n+++ b/a\n@@ -1,2 +1,2 @@\n-old\n+new\n", 410)

    def test_adaptive_split_preserves_original_long_line_offsets(self):
        content = "0123456789" * 1000
        batches, _ = plan_batches(f"--- a/a\n+++ b/a\n@@ -2,0 +3 @@\n+{content}\n", 800)
        plan = {"batches": batches}
        parent = batches[1]
        original_offset = parent["ranges"][0]["offset"]
        self.assertGreater(original_offset, 0)
        last_id = max(batch["id"] for batch in batches)
        self.assertTrue(BatchReview._split_batch(plan, 1))
        children = [batch for batch in plan["batches"] if batch["id"] > last_id]
        self.assertEqual(original_offset, children[0]["ranges"][0]["offset"])
        self.assertEqual(parse_changes(parent["diff"])[0][0].text, "".join(
            row.text for batch in children for row in parse_changes(batch["diff"])[0]
        ))


class BatchedServiceTests(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.settings = Settings(
            host="127.0.0.1", port=8080, db_path=self.path, max_diff_bytes=100000,
            max_steps=8, timeout_seconds=10, llm_base_url="", llm_api_key="", llm_model="",
            github_webhook_secret="", github_token="", auto_post_review=False,
        )

    def tearDown(self):
        if hasattr(self, "service"):
            self.service.queue.close()
        os.unlink(self.path)

    def create_service(self, **options):
        self.service = enable_agentic_service(ReviewService(replace(self.settings, **options)))
        return self.service

    def test_zero_divisor_regression_survives_an_empty_model_review(self):
        service = self.create_service()

        class Client(FakeAgenticClient):
            def complete_json(self, role, system, user, ledger=None, max_tokens=None):
                result = super().complete_json(role, system, user, ledger, max_tokens=max_tokens)
                if role == "critic":
                    result["decisions"] = []
                if role == "lead" and "accepted_finding_indices" in result:
                    result["accepted_finding_indices"] = []
                return result

        service.chat_client = Client()
        diff = (
            "--- a/calc.py\n+++ b/calc.py\n@@ -4,3 +4,3 @@\n"
            " def divide(total: float, count: int) -> float:\n"
            "     \"\"\"Return a safe per-item average.\"\"\"\n"
            "-    return total / count if count else 0\n"
            "+    return total / count\n"
        )
        result = service.create_review("org/repo", diff)
        self.assertEqual("SUCCESS", result["state"])
        finding, = result["report"]["findings"]
        self.assertEqual((ZERO_DIVISOR_GUARD_RULE, "calc.py", 6),
                         (finding["rule_id"], finding["path"], finding["line"]))
        self.assertTrue(finding["gate"]["passed"])

    def test_discount_guard_findings_stay_stable_across_worker_outputs(self):
        service = self.create_service()
        diff = (
            "--- a/discount.py\n+++ b/discount.py\n@@ -4,5 +4,3 @@\n"
            " def apply_discount(price, percent):\n"
            "-    if percent < 0 or percent > 100:\n"
            "-        raise ValueError('outside the range')\n"
            "     discounted = price * (1 - percent / 100)\n"
            "-    return max(0.0, round(discounted, 2))\n"
            "+    return round(discounted, 2)\n"
        )
        expected = {(INPUT_RANGE_GUARD_RULE, 5, "old"), (ZERO_FLOOR_RULE, 6, "new")}

        class Client(FakeAgenticClient):
            def complete_json(self, role, system, user, ledger=None, max_tokens=None):
                result = super().complete_json(role, system, user, ledger, max_tokens=max_tokens)
                if role == "security":
                    result["findings"] = [{
                        "rule_id": "SEC-INPUT-VALIDATION", "title": "Removed percent bounds check",
                        "explanation": "Out-of-range discounts reach the calculation.",
                        "path": "discount.py", "line": 6, "line_side": "new",
                        "evidence": "return round(discounted, 2)",
                    }]
                if role == "correctness-reliability":
                    result["findings"] = [{
                        "rule_id": "COR-INVARIANT", "title": "Result is no longer clamped to zero",
                        "explanation": "The final price can be negative.",
                        "path": "discount.py", "line": 8, "line_side": "old",
                        "evidence": "return max(0.0, round(discounted, 2))",
                    }]
                return result

        for client in (FakeAgenticClient(), Client()):
            with self.subTest(client=type(client).__name__):
                service.chat_client = client
                result = service.create_review("org/repo", diff)
                self.assertEqual("SUCCESS", result["state"])
                findings = result["report"]["findings"]
                self.assertEqual(2, len(findings))
                self.assertEqual(expected, {(f["rule_id"], f["line"], f["line_side"]) for f in findings})
                self.assertTrue(all(f["gate"]["passed"] for f in findings))

    def test_budget_pause_resumes_only_unfinished_and_confirmation_is_idempotent(self):
        service = self.create_service(review_task_token_budget=6200)
        calls = []

        class Client(FakeAgenticClient):
            def complete_json(self, role, system, user, ledger=None, max_tokens=None):
                task = json.loads(json.loads(user)["task"])
                calls.append((role, task.get("phase"), task.get("change_overview", {}).get("batch_id")))
                ledger.record_model(role, self.provider, self.model, {"input_tokens": 250, "output_tokens": 50}, 1)
                return super().complete_json(role, system, user, None, max_tokens=max_tokens)

        service.chat_client = Client()
        diff = "".join(f"--- a/file{i}.txt\n+++ b/file{i}.txt\n@@ -1 +1 @@\n-old\n+{'abcde' * 600}\n" for i in range(12))
        result = service.create_review("org/repo", diff)
        task_id = result["task_id"]
        self.assertEqual("PAUSED_BUDGET", result["state"])
        paused = service.batch_review.details(service.store.get(task_id), True)
        complete_ids = [b["id"] for b in paused["coverage"]["batches"] if b["status"] == "completed"]
        self.assertTrue(complete_ids)
        self.assertLess(len(complete_ids), paused["coverage"]["total"])
        self.assertFalse(paused["partial_report"]["execution"]["coverage"]["complete"])
        with self.assertRaises(ReviewConflict):
            service.accept_review(task_id, "default", "reviewer", "wrong-revision")
        before_resume = len(calls)
        service.resume_task(task_id, "default", 40000)
        deadline = time.monotonic() + 10
        task = service.store.get(task_id)
        while task["state"] not in {"FAILED", "SUCCESS"} and time.monotonic() < deadline:
            time.sleep(.03)
            task = service.store.get(task_id)
        self.assertEqual("SUCCESS", task["state"], task["error"])
        self.assertTrue(task["report"]["execution"]["coverage"]["complete"])
        self.assertFalse(set(complete_ids) & {bid for _, _, bid in calls[before_resume:]})
        self.assertFalse(any(phase == "overview" for _, phase, _ in calls[before_resume:]))
        detail = service.batch_review.details(task, True)
        accepted = service.accept_review(task_id, "default", "reviewer", detail["report_revision"])
        self.assertEqual(accepted, service.accept_review(task_id, "default", "second", detail["report_revision"]))
        self.assertEqual("reviewer", accepted["actor"])
        with self.assertRaisesRegex(ValueError, "not found"):
            service.accept_review(task_id, "other", "second", detail["report_revision"])

    def test_invalid_action_is_corrected_once_without_changing_coverage(self):
        service = self.create_service()
        corrections = []

        class Client(FakeAgenticClient):
            def complete_json(self, role, system, user, ledger=None, max_tokens=None):
                task = json.loads(json.loads(user)["task"])
                if task.get("phase") == "delegate":
                    corrections.append(system)
                    if len(corrections) == 1:
                        ledger.record_model(role, self.provider, self.model, {"input_tokens": 80, "output_tokens": 10}, 1)
                        return {"delegations": []}
                return super().complete_json(role, system, user, ledger, max_tokens=max_tokens)

        service.chat_client = Client()
        result = service.create_review("org/repo", DIFF)
        self.assertEqual(2, len(corrections))
        self.assertIn("required complete JSON object", corrections[1])
        self.assertTrue(result["report"]["execution"]["coverage"]["complete"])

    def test_prompt_passes_evaluation_without_activating_and_rejected_cannot_publish(self):
        service = self.create_service()
        store = service.store
        # Isolate the evaluation policy from the built-in examples.
        with store._connect() as connection:
            connection.execute("DELETE FROM evaluation_cases")
        store.save_evaluation_case("positive", "validation", DIFF, [{"path": "a.py", "line": 5}], "test")
        store.save_evaluation_case("clean", "holdout", DIFF.replace("new_value", "other_value"), [], "test")

        class CandidateReviewer:
            def __init__(self, prompt):
                self.prompt = prompt

            def review(self, diff, parsed):
                if "candidate" in self.prompt and "+new_value" in diff:
                    return [Finding("QUALITY-UNFINISHED", Severity.MEDIUM, "issue", "explanation", "a.py", 5,
                                    "new_value", "fix", "test")]
                return []

        service.evolution = EvolutionEngine(store, CandidateReviewer, min_cases=1, min_holdout_cases=1,
                                            max_cases=2, seed_defaults=False)
        job = service.queue_evolution("prompt", "llm-review", "default", "admin", {
            "prompt": "candidate: Review the diff and return JSON with severity, fix and test.",
        })
        deadline = time.monotonic() + 5
        running = service.evolution_job(job["job_id"], "default")
        while running["state"] in {"PENDING", "EXECUTING"} and time.monotonic() < deadline:
            time.sleep(.03)
            running = service.evolution_job(job["job_id"], "default")
        self.assertEqual("SUCCESS", running["state"], running["error"])
        self.assertEqual("ready", running["result"]["decision"])
        self.assertIsNone(service.evolution_job(job["job_id"], "other"))
        self.assertIsNone(store.get_active_skill_version("llm-review"))
        version = running["result"]["version"]["version"]
        rejected = store.save_skill_version("llm-review", "untested candidate", 1)
        with self.assertRaises(ReviewConflict):
            service.publish_version("prompt", "llm-review", rejected["version"], "default", "admin")
        service.publish_version("prompt", "llm-review", version, "default", "admin", canary_percent=10)
        self.assertIsNone(store.get_active_skill_version("llm-review"))
        service.publish_version("prompt", "llm-review", version, "default", "admin")
        self.assertEqual(version, store.get_active_skill_version("llm-review")["version"])
        self.assertEqual("stopped", store.get_deployment("default", "llm-review")["status"])

    def test_calc_zero_division_findings_survive_batched_skills_and_gates(self):
        calc_diff = (
            "--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n"
            " def divide(total, count):\n"
            "-    return total / count if count else 0\n"
            "+    return total / count\n"
        )
        service = self.create_service(skills_dir="skills")
        seen_skills = []

        class CalcClient(FakeAgenticClient):
            def complete_json(self, role, system, user, ledger=None, max_tokens=None):
                if ledger:
                    ledger.record_model(
                        role, self.provider, self.model,
                        {"prompt_tokens": 80, "completion_tokens": 40}, 1,
                    )
                task = json.loads(json.loads(user)["task"])
                if role == "lead" and task.get("phase") == "delegate":
                    return {
                        "action": "final",
                        "delegations": [
                            {
                                "assignment_id": "rel-1",
                                "worker": "correctness-reliability",
                                "objective": "Check boundary and test coverage",
                                "skills": ["code-quality", "correctness-review", "test-quality"],
                            }
                        ],
                        "risk_level": "normal",
                    }
                if role == "correctness-reliability":
                    seen_skills.extend(
                        item["name"] for item in task.get("active_agent_skills") or []
                    )
                    return {
                        "action": "final",
                        "findings": [
                            {
                                "rule_id": "COR-BOUNDARY-CONDITION",
                                "severity": "high",
                                "title": "count == 0 now raises ZeroDivisionError instead of returning 0",
                                "observed_result": "Removing the zero guard raises ZeroDivisionError when count is 0.",
                                "path": "calc.py",
                                "line": 2,
                                "evidence": "+    return total / count",
                                "recommended_fix": "Restore explicit handling for count == 0.",
                                "recommended_test": "Assert divide(10, 0) behavior.",
                            },
                            {
                                "rule_id": "TEST-COVERAGE",
                                "severity": "low",
                                "title": "Changed count == 0 behavior lacks a regression test",
                                "behavior_at_risk": "Zero-denominator behavior changed without test coverage.",
                                "path": "calc.py",
                                "line": 2,
                                "evidence": "-    return total / count if count else 0",
                                "recommended_fix": "Add a unit test covering count == 0.",
                                "recommended_test": "Test divide(total, 0).",
                            },
                        ],
                    }
                if role == "critic":
                    return {
                        "action": "final",
                        "decisions": [
                            {
                                "finding_index": idx,
                                "accepted": True,
                                "objections": [],
                                "confidence_adjustment": -0.05,
                            }
                            for idx in range(len(task["candidates"]))
                        ],
                    }
                return super().complete_json(role, system, user, None, max_tokens=max_tokens)

        service.chat_client = CalcClient()
        result = service.create_review("demo/calc", calc_diff)
        self.assertEqual("SUCCESS", result["state"])
        self.assertEqual(["correctness-review", "test-quality"], seen_skills)
        guard, = result["report"]["findings"]
        self.assertIn("ZeroDivisionError", guard["title"])
        self.assertEqual(ZERO_DIVISOR_GUARD_RULE, guard["rule_id"])
        self.assertEqual(["local-rule-scanner", "correctness-reliability"], guard["sources"])
        self.assertIn("regression test for count=0", guard["test"])
        self.assertIn("assert the original fallback", guard["test"])
