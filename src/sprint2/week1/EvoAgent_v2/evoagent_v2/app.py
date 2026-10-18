from __future__ import annotations

import hashlib
import hmac
import json
import re
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import ROOT, Settings
from .github import GitHubClient
from .llm import ChatCompletionsClient
from .models import MODES
from .store import Store
from .workflow import WorkflowEngine


STATIC = ROOT / "static"
PR_URL = re.compile(
    r"^https?://github\.com/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(?P<number>[1-9][0-9]*)/?$",
    re.IGNORECASE,
)


def verify_webhook_signature(secret: str, body: bytes, signature: str) -> bool:
    if not secret or not signature:
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def markdown_report(report: dict) -> str:
    lines = ["## EvoAgent V2 review", "", report.get("summary") or "No summary.", ""]
    if not report.get("findings"):
        return "\n".join(lines + ["No evidence-backed finding."])
    for item in report["findings"]:
        lines.extend(
            [
                f"### [{item['severity'].upper()}] {item['title']}",
                f"`{item['path']}:{item['line']}`",
                "",
                item["explanation"],
                "",
                "**Evidence:** `" + item["evidence"].replace("`", "'") + "`",
                "",
                "**Fix:** " + item["fix"],
                "",
                "**Test:** " + item["test"],
                "",
            ]
        )
    return "\n".join(lines)


class ReviewCoordinator:
    def __init__(self, settings: Settings, store: Store, github=None, workflow=None):
        self.settings = settings
        self.store = store
        self.github = github or GitHubClient(settings.github_token, settings.timeout_seconds)
        llm = ChatCompletionsClient(settings.llm_url, settings.llm_api_key, settings.llm_model, settings.timeout_seconds)
        self.workflow = workflow or WorkflowEngine(llm, store)
        self.pool = ThreadPoolExecutor(max_workers=settings.worker_count, thread_name_prefix="evoagent-v2")

    def enqueue(self, repository: str, number: int, source: str, mode: str) -> str:
        if mode not in MODES:
            raise ValueError("mode must be baseline or collaborative")
        if not self.settings.llm_ready:
            raise ValueError("Configure the V2 model URL, API key, and model first")
        task_id = self.store.create_task(repository, number, source, mode)
        self.pool.submit(self._run, task_id, repository, number, mode)
        return task_id

    def _run(self, task_id: str, repository: str, number: int, mode: str) -> None:
        self.store.set_running(task_id)
        try:
            pull = self.github.pull_request(repository, number)
            if str(pull.get("state", "")).lower() != "open":
                raise ValueError("PR does not exist, is inaccessible, or is closed")
            diff = self.github.diff(str(pull.get("diff_url", "")))
            size = len(diff.encode("utf-8"))
            if size > self.settings.max_diff_bytes:
                raise ValueError(
                    f"Diff is {size} bytes, above the configured {self.settings.max_diff_bytes}-byte limit; it was not silently truncated"
                )
            report, metrics = self.workflow.review(task_id, repository, number, diff, mode)
            metrics["diff_bytes"] = size
            self.store.set_success(task_id, report, metrics)
        except Exception as exc:
            self.store.set_failed(task_id, str(exc))
            return
        if self.settings.auto_post_review:
            try:
                self.github.comment(repository, number, markdown_report(report))
                self.store.set_delivery(task_id, "SUCCESS")
            except Exception as exc:
                self.store.set_delivery(task_id, "FAILED", str(exc))


class Application:
    def __init__(self, settings: Settings, store: Store | None = None, coordinator: ReviewCoordinator | None = None):
        self.settings = settings
        self.store = store or Store(settings.db_path)
        self.recovered_tasks = self.store.recover_interrupted()
        self.coordinator = coordinator or ReviewCoordinator(settings, self.store)

    def status(self) -> dict:
        return {
            "service": "EvoAgent V2",
            "version": "2.0.0",
            "modes": sorted(MODES),
            "llm_configured": self.settings.llm_ready,
            "github_token_configured": bool(self.settings.github_token),
            "webhook_secret_configured": bool(self.settings.github_webhook_secret),
            "auto_post_review": self.settings.auto_post_review,
            "tls": Settings.tls_diagnostics(),
            "recovered_interrupted_tasks": self.recovered_tasks,
        }


def read_json(handler: BaseHTTPRequestHandler, maximum: int) -> dict:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except ValueError as exc:
        raise ValueError("Invalid Content-Length") from exc
    if length < 0 or length > maximum:
        raise ValueError(f"Request body exceeds the {maximum}-byte limit")
    body = handler.rfile.read(length)
    value = json.loads(body.decode("utf-8")) if body else {}
    if not isinstance(value, dict):
        raise ValueError("JSON body must be an object")
    return value


def handler_for(app: Application):
    class Handler(BaseHTTPRequestHandler):
        server_version = "EvoAgent-V2/2.0"

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def send_json(self, status: int, value: Any) -> None:
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/health":
                self.send_json(200, app.status())
                return
            if path == "/api/tasks":
                self.send_json(200, {"tasks": app.store.list_tasks()})
                return
            if path.startswith("/api/tasks/"):
                task = app.store.get(path.rsplit("/", 1)[-1])
                self.send_json(200 if task else 404, task or {"error": "task not found"})
                return
            relative = "index.html" if path in {"", "/"} else path.lstrip("/")
            candidate = (STATIC / relative).resolve()
            if STATIC not in candidate.parents or not candidate.is_file():
                self.send_json(404, {"error": "not found"})
                return
            mime = {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
            }.get(candidate.suffix, "application/octet-stream")
            body = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                if path in {"/api/reviews/from-pr", "/api/reviews/compare"}:
                    payload = read_json(self, app.settings.max_request_bytes)
                    match = PR_URL.fullmatch(str(payload.get("pull_request_url", "")).strip())
                    if not match:
                        raise ValueError("Enter a GitHub PR URL such as https://github.com/owner/repo/pull/42")
                    repository, number = match.group("repository"), int(match.group("number"))
                    if path.endswith("/compare"):
                        task_ids = {
                            mode: app.coordinator.enqueue(repository, number, "compare", mode)
                            for mode in ("baseline", "collaborative")
                        }
                        self.send_json(202, {"task_ids": task_ids})
                    else:
                        mode = str(payload.get("mode", "collaborative"))
                        task_id = app.coordinator.enqueue(repository, number, "pr-url", mode)
                        self.send_json(202, {"task_id": task_id, "mode": mode, "state": "PENDING"})
                    return
                if path == "/webhooks/github":
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                    except ValueError as exc:
                        raise ValueError("Invalid Content-Length") from exc
                    if length < 0 or length > app.settings.max_request_bytes:
                        raise ValueError("Webhook body is too large")
                    body = self.rfile.read(length)
                    if not verify_webhook_signature(
                        app.settings.github_webhook_secret, body, self.headers.get("X-Hub-Signature-256", "")
                    ):
                        self.send_json(401, {"error": "invalid webhook signature"})
                        return
                    if not app.store.remember_delivery(self.headers.get("X-GitHub-Delivery", "")):
                        self.send_json(200, {"status": "duplicate delivery ignored"})
                        return
                    payload = json.loads(body.decode("utf-8"))
                    action = str(payload.get("action", ""))
                    if self.headers.get("X-GitHub-Event") != "pull_request" or action not in {"opened", "reopened", "synchronize"}:
                        self.send_json(200, {"status": "event ignored"})
                        return
                    pull = payload.get("pull_request") or {}
                    repository = payload.get("repository") or {}
                    task_id = app.coordinator.enqueue(
                        str(repository.get("full_name", "")), int(pull.get("number", 0)), "github-webhook", "collaborative"
                    )
                    self.send_json(202, {"task_id": task_id, "mode": "collaborative", "state": "PENDING"})
                    return
                self.send_json(404, {"error": "not found"})
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)[:1000]})

    return Handler


def run() -> None:
    settings = Settings.from_env()
    app = Application(settings)
    server = ThreadingHTTPServer((settings.host, settings.port), handler_for(app))
    print(f"EvoAgent V2: http://{settings.host}:{settings.port}")
    server.serve_forever()
