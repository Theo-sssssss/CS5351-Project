"""Compare the legacy and batched production review paths on the same cases."""

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evoagent.config import Settings
from evoagent.evaluation_harness import EndToEndEvaluationHarness, load_jsonl
from evoagent.harness import ReviewHarness
from evoagent.service import ReviewService


class ServiceReviewer:
    def __init__(self, service):
        self.service = service
        self.name = "batched" if service.settings.review_batching_enabled else "legacy"
        self.runs = {}

    def review_case(self, case, _parsed):
        start = time.monotonic()
        run = {"id": case["id"], "coverage": None}
        self.runs[case["id"]] = run
        try:
            result = self.service.create_review(case["repository"], case["diff"], source="engine-benchmark")
            task = self.service.store.get(result["task_id"])
            details = self.service.batch_review.details(task, False)
            report = details.get("report") or details.get("partial_report") or {}
            execution = report.get("execution", {})
            coverage = details["coverage"]
            run.update(state=result["state"],
                       tokens=details.get("budget", {}).get("charged_tokens", execution.get("total_tokens")),
                       coverage=None if coverage is None else {
                           key: coverage[key] for key in ("complete", "completed", "total")
                       })
            if result["state"] != "SUCCESS":
                raise RuntimeError("review finished in " + result["state"])
            return [ReviewHarness._finding_from_dict(item) for item in report["findings"]]
        finally:
            run["seconds"] = round(time.monotonic() - start, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", help="Human-labelled JSONL in the end-to-end evaluation schema")
    parser.add_argument("--limit", type=int, default=0, help="Limit paired cases for a pilot run")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit cannot be negative")
    cases = load_jsonl(args.dataset)
    if args.limit:
        cases = cases[:args.limit]
    if not cases:
        parser.error("No cases selected")
    settings = Settings.from_env()
    if not settings.resolved_llm():
        parser.error("Configure the same model for both review engines using the EvoAgent environment settings")

    reports = {}
    with tempfile.TemporaryDirectory(prefix="evoagent-engine-benchmark-") as directory:
        for enabled in (False, True):
            config = replace(settings, db_path=os.path.join(directory, f"{int(enabled)}.db"),
                             database_url="", redis_url="", memory_enabled=False, auto_post_review=False,
                             review_batching_enabled=enabled)
            service = ReviewService(config)
            try:
                reviewer = ServiceReviewer(service)
                result = EndToEndEvaluationHarness().run(reviewer, cases)
                result["execution"] = list(reviewer.runs.values())
                reports[reviewer.name] = result
            finally:
                service.queue.close()
    model = settings.resolved_llm()
    print(json.dumps({"provider": model["provider"], "model": model["model"],
                      "task_token_budget": settings.review_task_token_budget, "arms": reports}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
