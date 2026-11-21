"""GitHub PR intake, commit identity, and opt-in review publication."""

import hashlib
import re
from urllib.parse import urlsplit

from .batch_review import ReviewConflict
from .metrics import metrics
from .report import to_markdown
from .store import utc_now
from .task_queue import PermanentTaskError, QueueLeaseBusy


REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+")
SHA = re.compile(r"[0-9a-f]{40}")


def parse_pr_url(url):
    if not isinstance(url, str) or len(url) > 500:
        raise ValueError("Enter a GitHub pull request URL")
    parsed = urlsplit(url.strip())
    match = re.fullmatch(r"/([^/]+/[^/]+)/pull/([1-9]\d{0,9})(?:/(?:files|commits))?/?", parsed.path)
    if (parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or not match
            or not REPOSITORY.fullmatch(match[1]) or match[1].split("/")[1] in {".", ".."}
            or int(match[2]) > 2147483647):
        raise ValueError("Use an https://github.com/owner/repository/pull/123 URL")
    return match[1].lower(), int(match[2])


class GitHubReview:
    def __init__(self, service):
        self.service = service
        self.store = service.store

    def enqueue_url(self, url, tenant):
        repository, number = parse_pr_url(url)
        self.service._require_agentic_model()
        self.service._authorize_repository(tenant, repository)
        if tenant != self.service.settings.default_tenant_id and not self.store.has_repository_grant(tenant, repository):
            raise PermissionError("This tenant must have an explicit grant for the GitHub repository")
        pull = self.service.github.get_pull_request(repository, number)
        return self.enqueue(repository, number, pull, tenant, None, "github-url")

    def enqueue(self, repository, number, pull, tenant, installation, source):
        if not REPOSITORY.fullmatch(repository) or repository.split("/")[1] in {".", ".."} or type(number) is not int or not 0 < number <= 2147483647:
            raise ValueError("Invalid GitHub repository or PR number")
        repository = repository.lower()
        self.service._authorize_repository(tenant, repository)
        head = (pull.get("head") or {}).get("sha")
        base = (pull.get("base") or {}).get("sha")
        pinned = all(isinstance(value, str) and SHA.fullmatch(value) for value in (head, base))
        if not pinned and (source == "github-url" or head or base):
            raise ValueError("GitHub did not return a valid base and head commit")
        api = f"https://api.github.com/repos/{repository}"
        data = {"diff_url": f"{api}/pulls/{number}", "head_sha": head if pinned else None,
                "base_sha": base if pinned else None, "pr_updated_at": pull.get("updated_at"), "github": {
                    "github_issue_url": f"{api}/issues/{number}", "installation_id": installation,
                    "url": f"https://github.com/{repository}/pull/{number}",
                }}
        # Older webhook fixtures lacked SHAs and expect their signed payload URL.
        if not pinned:
            data["diff_url"] = pull.get("diff_url") or data["diff_url"]
            data["github"]["github_issue_url"] = pull.get("issue_url", "")
        key = f"github-pr:{tenant}:{repository}:{number}"
        with self.store.review_lock(key) as locked:
            if not locked:
                raise ReviewConflict("This PR is already being queued. Try again shortly.")
            existing = self.store.pr_snapshot_task(tenant, repository, number, head, base) if pinned else None
            if existing:
                task_id, state = existing["id"], existing["state"]
                if state == "PENDING":
                    self.service.queue.submit(self.service._review_message(self.store.get(task_id, tenant)), message_id=task_id)
            else:
                task_id = self.service._create_deferred_task(repository, number, source, tenant, data)
                self.service.queue.submit(self.service._review_message(self.store.get(task_id, tenant)), message_id=task_id)
                metrics.inc("reviews_enqueued_total")
                state = "PENDING"
        return {"task_id": task_id, "state": state, "duplicate": bool(existing), "queue": self.service.queue.backend,
                "will_post_to_github": self.publication_policy(tenant, repository) != "off"}

    def publication_policy(self, tenant, repository):
        value = self.store.repository_publication(tenant, repository)
        return value or ("summary" if self.service.settings.auto_post_review else "off")

    def publish(self, task, report, payload):
        tenant, repository, number = task["tenant_id"], task["repository"], task["pull_request"]
        policy = self.publication_policy(tenant, repository)
        data = task["input"]
        info = data.get("github") or payload
        if policy == "off" or not info.get("github_issue_url") or number is None:
            return
        saved = self.store.workbench_checkpoints(task["id"], ("review-github-posted",)).get("review-github-posted", {})
        if saved.get("state") in {"published", "stale"} or saved.get("posted_at"):
            return
        with self.store.review_lock(f"github-publish:{tenant}:{repository}:{number}") as locked:
            if not locked:
                raise QueueLeaseBusy() if self.service.settings.redis_url else RuntimeError("PR publication is busy")
            client = self.service.github_client_for_installation(info.get("installation_id"))
            head = data.get("head_sha")

            def current():
                if head:
                    try:
                        self.service._check_review_commit(client, task)
                    except PermanentTaskError:
                        self.store.save_checkpoint(task["id"], "review-github-posted", {"state": "stale"})
                        return False
                return True

            if not current():
                return
            try:
                api = info["github_issue_url"]
                text = (f"Review of commit `{head[:12]}`.\n\n" if head else "") + to_markdown(report.to_dict())
                client.upsert_comment(api, text[:60000], "<!-- evoagent-review-summary -->" if head else f"<!-- evoagent-review:{task['id']} -->")
                result = {"state": "published", "posted_at": utc_now(), "policy": policy}
                if policy == "inline" and head and current():
                    files, _ = self.service.workbench._files(task)
                    rows = self.service.workbench._finding_rows(task, report.to_dict(), files)
                    eligible = []
                    for row in rows:
                        if not row["file_id"]:
                            continue
                        file = files[row["file_id"]]
                        path = file["new_path"] if file["new_path"] != "/dev/null" else file["old_path"]
                        anchor = hashlib.sha256(f"{head}:{data.get('base_sha')}:{path}:{row['id']}".encode()).hexdigest()[:24]
                        eligible.append({"path": path, "line": row["line"], "side": "LEFT" if row.get("line_side") == "old" else "RIGHT",
                                         "marker": f"<!-- evoagent-inline:{anchor} -->",
                                         "body": f"**{row['severity']} · {row['title']}**\n\n{row['explanation']}"[:5000]})
                    result.update(client.publish_inline_findings(repository, number, head, eligible[:12]))
                    result["inline_skipped"] += len(rows) - min(12, len(eligible))
                if policy == "inline" and head and not current():
                    return
                self.store.save_checkpoint(task["id"], "review-github-posted", result)
            except Exception:
                self.store.save_checkpoint(task["id"], "review-github-posted", {"state": "failed", "policy": policy})
                raise
