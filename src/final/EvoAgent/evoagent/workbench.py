"""Task progress, code context and finding dispositions for the review UI."""

import hashlib
import json
from collections import Counter, defaultdict
from functools import lru_cache

from .batch_review import ENGINE, METER, ReviewConflict
from .models import TaskState
from .review_batches import parse_changes
from .store import utc_now


def _fingerprint(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()[:32]


@lru_cache(maxsize=4)
def diff_files(diff):
    rows, metadata = parse_changes(diff)
    files = {}
    for row in rows:
        key = _fingerprint(row.old_path, row.new_path)
        if key not in files:
            files[key] = {"id": key, "path": row.path, "old_path": row.old_path, "new_path": row.new_path, "rows": []}
        files[key]["rows"].append(row)
    for key, file in files.items():
        file["lines"] = len(file["rows"])
        file["added"] = sum(row.side == "+" for row in file["rows"])
        file["removed"] = sum(row.side == "-" for row in file["rows"])
        file["anchors"] = {("old" if row.side == "-" else "new", row.line): (index, row)
                           for index, row in enumerate(file["rows"]) if row.side != " "}
        file["counts"] = Counter((row.side, row.text) for row in file["rows"] if row.side != " ")
    for item in metadata:
        if not any(item["path"] in (file["old_path"], file["new_path"]) for file in files.values()):
            key = _fingerprint(item["path"], item["kind"])
            files[key] = {"id": key, "path": item["path"], "old_path": item["path"], "new_path": item["path"],
                          "lines": 0, "added": 0, "removed": 0, "rows": [], "anchors": {}, "counts": {}, "kind": item["kind"]}
    return files


class ReviewWorkbench:
    def __init__(self, service):
        self.service = service
        self.store = service.store

    def header(self, task_id, tenant):
        task = self.store.task_header(task_id, tenant)
        if not task or task["input"].get("job_type") or not self.store.repository_allowed(tenant, task["repository"]):
            raise LookupError("Review task not found")
        return task

    def tasks(self, tenant, repository, pull_request, state, page):
        if len(repository) > 250 or state and state not in {item.value for item in TaskState}:
            raise ValueError("Invalid repository or task state filter")
        if not 1 <= page <= 1000000 or pull_request is not None and not 0 < pull_request <= 2147483647:
            raise ValueError("Invalid page or pull request number")
        size = 20
        rows = self.store.workbench_tasks(tenant, repository, pull_request, state, size, (page - 1) * size)
        return {"tasks": rows[:size], "page": page, "has_next": len(rows) > size}

    def progress(self, task, may_review, may_fix):
        data = task["input"]
        state = task["state"]
        batched = data.get("review_engine") == ENGINE
        saved = self.store.workbench_checkpoints(task["id"], (
            METER, "review-v2-current", "review-v2-confirmation", "workbench-version-summary", "review-github-posted", "workbench-pr-stale",
        ))
        total, completed = self.store.task_coverage_counts(task["id"]) if batched else (None, 0)
        coverage = {"total": total or 0, "completed": completed, "complete": total is not None and total == completed} if batched else None
        latest = self.store.pr_tasks(task["tenant_id"], task["repository"], task["pull_request"], 1) if data.get("head_sha") else []
        publication = saved.get("review-github-posted") or {}
        stale = bool(saved.get("workbench-pr-stale") or publication.get("state") == "stale" or latest and
                     (latest[0]["head_sha"], latest[0]["base_sha"]) != (data.get("head_sha"), data.get("base_sha")))
        confirmation = saved.get("review-v2-confirmation")
        error = task["error"] if state == "FAILED" else None
        current = saved.get("review-v2-current") or {}
        code = current.get("error_code")
        if current.get("id") and state in {"EXECUTING", "PAUSED_BUDGET", "FAILED"}:
            current["phase"] = self.store.task_batch_phase(task["id"], current["id"])
        return {
            **{key: task[key] for key in ("id", "repository", "pull_request", "state", "updated_at", "cancel_requested", "has_report")},
            "coverage": coverage, "error": error, "error_code": code, "confirmation": confirmation, "stale": stale,
            "head_sha": data.get("head_sha"), "github_url": (data.get("github") or {}).get("url"),
            "current": current, "versions": saved.get("workbench-version-summary"), "publication": publication,
            "budget": {"limit": data.get("initial_token_budget", self.service.settings.review_task_token_budget)
                         + int(data.get("additional_budget_tokens", 0)), **saved.get(METER, {})} if batched else None,
            "actions": {
                "review": may_review,
                "accept": may_review and not confirmation and state == "SUCCESS" and bool(total) and total == completed,
                "resume": may_review and not task["cancel_requested"] and state in {"FAILED", "PAUSED_BUDGET"} and not stale,
                "cancel": may_review and not task["cancel_requested"] and state in {"PENDING", "PLANNING", "EXECUTING", "REVIEWING", "PAUSED_BUDGET"},
                "fix": may_fix and task["has_report"] and task["pull_request"] is not None and not stale
                       and self.store.repository_allowed(task["tenant_id"], task["repository"], True),
            },
        }

    def _files(self, task):
        diff = self.store.get_task_payload(task["id"])
        if not diff:
            return {}, "Diff is not available yet"
        try:
            return diff_files(diff), None
        except ValueError:
            return {}, "Stored Diff is not a supported unified Diff"

    @staticmethod
    def _finding_rows(task, report, files):
        lookup = defaultdict(list)
        for file in files.values():
            lookup[("old", file["old_path"])].append(file)
            lookup[("new", file["new_path"])].append(file)
        rows = []
        for index, finding in enumerate(report.get("findings", [])):
            path, line = finding.get("path"), finding.get("line")
            side = finding.get("line_side", "new")
            key = _fingerprint(path, side, line, finding.get("rule_id"), index)
            anchors = [(file, file["anchors"][(side, line)][1]) for file in lookup[(side, path)]
                       if (side, line) in file["anchors"]]
            shared_key, file_id = None, None
            if len(anchors) == 1:
                file, row = anchors[0]
                file_id = file["id"]
                evidence = str(finding.get("evidence") or "").strip()
                if evidence and evidence in row.text and file["counts"][(row.side, row.text)] == 1:
                    shared_key = _fingerprint(path, side, finding.get("rule_id"), row.text)
            rows.append({**finding, "id": key, "file_id": file_id, "shared_key": shared_key, "index": index})
        counts = Counter(item["shared_key"] for item in rows)
        pr_scope = ("pr:" + _fingerprint(task["repository"], task["pull_request"])) if task["input"].get("head_sha") else None
        for row in rows:
            shared_key = row.pop("shared_key")
            shared = pr_scope and shared_key and counts[shared_key] == 1 and task["state"] == "SUCCESS"
            row["scope"] = pr_scope if shared else "task:" + task["id"]
            row["key"] = shared_key if shared else row["id"]
        return rows

    def content(self, task, may_review):
        full = self.store.get(task["id"], task["tenant_id"])
        details = self.service.batch_review.details(full, may_review)
        report = details.get("report") or details.get("partial_report")
        files, diff_error = self._files(task)
        rows = self._finding_rows(task, report or {}, files)
        scopes = sorted({row["scope"] for row in rows})
        states = self.store.finding_dispositions(task["tenant_id"], scopes) if scopes else {}
        for row in rows:
            decision = states.get((row.pop("scope"), row.pop("key")))
            row["disposition"] = {key: decision[key] for key in ("state", "actor", "note", "updated_at")} if decision else {"state": "pending"}
        return {"report": {"findings": rows, "summary": report.get("summary"), "collaboration": {
                            "agent_skills": report.get("collaboration", {}).get("agent_skills", []),
                        }} if report else None,
                "partial": not details.get("report") and bool(report), "report_revision": details.get("report_revision"),
                "fix_result": self.store.workbench_checkpoints(task["id"], ("workbench-fix",)).get("workbench-fix"),
                "coverage": details.get("coverage"), "trace": details.get("trace", []),
                "input": {"enabled_skills": task["input"].get("enabled_skills", [])},
                "files": [{key: value for key, value in file.items() if key not in {"rows", "anchors", "counts"}}
                          for file in files.values()], "diff_error": diff_error,
                "history": self.store.pr_tasks(task["tenant_id"], task["repository"], task["pull_request"]) if task["input"].get("head_sha") else []}

    def diff(self, task, file_id, offset, side, line):
        if side not in {"old", "new"} or line < 0 or offset < 0:
            raise ValueError("Invalid Diff location")
        files, error = self._files(task)
        if error:
            raise LookupError(error)
        file = files.get(file_id)
        if file is None:
            raise LookupError("Diff file not found")
        anchor = file["anchors"].get((side, line)) if line else None
        if anchor:
            offset = max(0, anchor[0] - 25)
        elif line:
            raise LookupError("Finding does not match a changed line in this file")
        rows, size, used = [], 100, 0
        for index, row in enumerate(file["rows"][offset:offset + size], offset):
            text = row.text[:12000]
            used += len(text.encode())
            if used > 115000 and rows and (not anchor or index > anchor[0]):
                break
            rows.append({"id": index, "kind": row.side, "hunk": row.hunk, "old": row.old_cursor if row.side != "+" else None,
                         "new": row.new_cursor if row.side != "-" else None, "text": text, "truncated": len(text) < len(row.text)})
        return {"path": file["path"], "rows": rows, "offset": offset, "total": file["lines"],
                "next_offset": offset + len(rows) if offset + len(rows) < file["lines"] else None,
                "anchor_id": anchor[0] if anchor else None}

    def set_finding(self, task, finding_id, state, note, actor):
        if (not isinstance(state, str) or state not in {"pending", "accepted", "false_positive", "fixed"}
                or not isinstance(note, str) or len(note) > 2000):
            raise ValueError("Invalid finding state or note")
        if task["state"] != "SUCCESS" or not task["has_report"]:
            raise ReviewConflict("Finding dispositions require a completed review")
        with self.store.review_lock(task["id"]) as acquired:
            if not acquired:
                raise ReviewConflict("This review is busy")
            full = self.store.get(task["id"], task["tenant_id"])
            files, _ = self._files(task)
            finding = next((item for item in self._finding_rows(task, full["report"], files) if item["id"] == finding_id), None)
            if not finding:
                raise LookupError("Finding not found")
            if self.store.finding_dispositions(task["tenant_id"], [finding["scope"]]).get(
                (finding["scope"], finding["key"]), {}
            ).get("state") != state and state == "false_positive":
                self.service.record_feedback(task["id"], state, full["report"]["findings"][finding["index"]], note, task["tenant_id"])
            self.store.save_finding_disposition(task["tenant_id"], finding["scope"], finding["key"], state, actor, note, utc_now())
            self.store.audit(task["tenant_id"], actor, "finding.disposition", task["id"], {"finding_id": finding_id, "state": state})
            return {"id": finding_id, "state": state}
