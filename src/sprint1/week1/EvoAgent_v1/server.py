"""GitHub PR reviewer built from one LLM API call and one prompt.

There is deliberately no agent planner, worker graph, tool loop, Skill system,
memory system, or autonomous retry policy in this application.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
PR_URL = re.compile(
    r"^https?://github\.com/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(?P<number>[1-9][0-9]*)/?$",
    re.IGNORECASE,
)
ALLOWED_SEVERITIES = {"critical", "high", "medium", "low"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE lines without replacing real environment values."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env(name: str, legacy: str = "", default: str = "") -> str:
    return os.getenv(name, os.getenv(legacy, default) if legacy else default).strip()


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    db_path: str
    github_token: str
    github_webhook_secret: str
    auto_post_review: bool
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    timeout_seconds: int
    public_base_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        return cls(
            host=env("PROMPT_REVIEW_HOST", default="127.0.0.1"),
            port=int(env("PROMPT_REVIEW_PORT", default="8082")),
            db_path=env("PROMPT_REVIEW_DB_PATH", default="prompt_review.db"),
            github_token=env("PROMPT_REVIEW_GITHUB_TOKEN", "EVOAGENT_GITHUB_TOKEN"),
            github_webhook_secret=env("PROMPT_REVIEW_GITHUB_WEBHOOK_SECRET", "EVOAGENT_GITHUB_WEBHOOK_SECRET"),
            auto_post_review=env("PROMPT_REVIEW_AUTO_POST_REVIEW", default="false").lower() == "true",
            llm_base_url=env("PROMPT_REVIEW_LLM_BASE_URL", "EVOAGENT_LLM_BASE_URL"),
            llm_api_key=env("PROMPT_REVIEW_LLM_API_KEY", "EVOAGENT_LLM_API_KEY"),
            llm_model=env("PROMPT_REVIEW_LLM_MODEL", "EVOAGENT_LLM_MODEL"),
            timeout_seconds=int(env("PROMPT_REVIEW_TIMEOUT_SECONDS", default="90")),
            public_base_url=env("PROMPT_REVIEW_PUBLIC_BASE_URL", default="http://127.0.0.1:8082"),
        )

    @property
    def llm_ready(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)


class Store:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, repository TEXT NOT NULL, pull_request INTEGER NOT NULL,
                    source TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, error TEXT NOT NULL DEFAULT '', report_json TEXT
                );
                CREATE TABLE IF NOT EXISTS deliveries (
                    delivery_id TEXT PRIMARY KEY, created_at TEXT NOT NULL
                );
            """)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def create_task(self, repository: str, number: int, source: str) -> str:
        task_id = str(uuid.uuid4())
        with self.lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO tasks(id,repository,pull_request,source,state,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (task_id, repository, number, source, "PENDING", now(), now()),
            )
        return task_id

    def update(self, task_id: str, state: str, report: Optional[dict] = None, error: str = "") -> None:
        with self.lock, self.connect() as conn:
            conn.execute(
                "UPDATE tasks SET state=?,updated_at=?,error=?,report_json=? WHERE id=?",
                (state, now(), error, json.dumps(report, ensure_ascii=False) if report else None, task_id),
            )

    def get(self, task_id: str) -> Optional[dict]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return self._row(row) if row else None

    def list_tasks(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100").fetchall()
        return [self._row(row) for row in rows]

    def remember_delivery(self, delivery_id: str) -> bool:
        if not delivery_id:
            return True
        try:
            with self.lock, self.connect() as conn:
                conn.execute("INSERT INTO deliveries(delivery_id,created_at) VALUES (?,?)", (delivery_id, now()))
            return True
        except sqlite3.IntegrityError:
            return False

    @staticmethod
    def _row(row: sqlite3.Row) -> dict:
        value = dict(row)
        value["report"] = json.loads(value.pop("report_json") or "null")
        return value


class GitHub:
    def __init__(self, token: str, timeout: int):
        self.token, self.timeout = token, timeout

    def request(self, url: str, accept: str = "application/vnd.github+json", method: str = "GET", body: bytes | None = None) -> Any:
        headers = {"Accept": accept, "User-Agent": "EvoPromptReview/1.0", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer %s" % self.token
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
        except HTTPError as exc:
            raise RuntimeError("GitHub returned HTTP %s" % exc.code) from exc
        except URLError as exc:
            raise RuntimeError("GitHub connection failed: %s" % exc.reason) from exc
        if "json" in accept:
            return json.loads(payload.decode("utf-8"))
        return payload.decode("utf-8")

    def pull_request(self, repository: str, number: int) -> dict:
        return self.request("https://api.github.com/repos/%s/pulls/%d" % (repository, number))

    def diff(self, url: str) -> str:
        return self.request(url, "application/vnd.github.v3.diff")

    def comment(self, repository: str, number: int, body: str) -> None:
        self.request(
            "https://api.github.com/repos/%s/issues/%d/comments" % (repository, number),
            method="POST", body=json.dumps({"body": body}).encode("utf-8"),
        )

    def create_webhook(self, repository: str, public_base_url: str, secret: str) -> dict:
        callback = public_base_url.rstrip("/") + "/webhooks/github"
        return self.request(
            "https://api.github.com/repos/%s/hooks" % repository,
            method="POST",
            body=json.dumps({
                "name": "web", "active": True, "events": ["pull_request"],
                "config": {"url": callback, "content_type": "json", "secret": secret, "insecure_ssl": "0"},
            }).encode("utf-8"),
        )


SYSTEM_PROMPT = """You are a senior code reviewer. Review only the supplied GitHub pull-request diff.
Return a single JSON object and no Markdown. Schema:
{
  "summary": "short Chinese summary",
  "risk": "critical|high|medium|low",
  "findings": [{
    "severity": "critical|high|medium|low", "title": "short Chinese title",
    "explanation": "why this change causes a concrete problem", "path": "changed file path",
    "line": 1, "evidence": "exact changed code", "fix": "concrete fix",
    "test": "regression test idea", "confidence": 0.0
  }]
}
Report only actionable defects introduced by changed lines. Do not invent repository context.
Do not report style preferences. If there is no actionable issue, return an empty findings list.
"""


def parse_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("LLM did not return a JSON object")
        value = json.loads(text[start:end + 1])
    if not isinstance(value, dict):
        raise ValueError("LLM response root must be an object")
    return value


def normalize_report(raw: dict, repository: str, number: int) -> dict:
    findings = []
    for item in raw.get("findings") or []:
        if not isinstance(item, dict):
            continue
        try:
            line = int(item.get("line", 0))
        except (TypeError, ValueError):
            line = 0
        severity = str(item.get("severity", "medium")).lower()
        findings.append({
            "severity": severity if severity in ALLOWED_SEVERITIES else "medium",
            "title": str(item.get("title", "Code review finding"))[:180],
            "explanation": str(item.get("explanation", ""))[:3000],
            "path": str(item.get("path", ""))[:500], "line": max(0, line),
            "evidence": str(item.get("evidence", ""))[:1000],
            "fix": str(item.get("fix", ""))[:3000], "test": str(item.get("test", ""))[:2000],
            "confidence": max(0, min(1, float(item.get("confidence", 0.7) or 0.7))),
        })
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda item: (rank[item["severity"]], item["path"], item["line"]))
    risk = str(raw.get("risk", "low")).lower()
    if findings:
        risk = findings[0]["severity"]
    return {
        "repository": repository, "pull_request": number, "reviewer": "prompt-api-reviewer",
        "review_method": "one LLM API call with one fixed prompt", "summary": str(raw.get("summary", ""))[:1500],
        "risk": risk if risk in ALLOWED_SEVERITIES else "low", "findings": findings,
        "created_at": now(),
    }


class PromptReviewer:
    def __init__(self, settings: Settings, store: Store):
        self.settings, self.store = settings, store
        self.github = GitHub(settings.github_token, settings.timeout_seconds)
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="prompt-review")

    def enqueue(self, repository: str, number: int, source: str) -> str:
        if not self.settings.github_token:
            raise ValueError("Configure PROMPT_REVIEW_GITHUB_TOKEN first")
        if not self.settings.llm_ready:
            raise ValueError("Configure PROMPT_REVIEW_LLM_BASE_URL, API_KEY, and MODEL first")
        task_id = self.store.create_task(repository, number, source)
        self.pool.submit(self._run, task_id, repository, number)
        return task_id

    def _run(self, task_id: str, repository: str, number: int) -> None:
        self.store.update(task_id, "RUNNING")
        try:
            pull = self.github.pull_request(repository, number)
            if str(pull.get("state", "")).lower() != "open":
                raise ValueError("PR does not exist, is inaccessible, or is closed")
            diff = self.github.diff(str(pull.get("diff_url", "")))
            report = self.review_diff(repository, number, diff)
            self.store.update(task_id, "SUCCESS", report=report)
            if self.settings.auto_post_review:
                self.github.comment(repository, number, markdown_report(report))
        except Exception as exc:
            self.store.update(task_id, "FAILED", error=str(exc)[:1000])

    def review_diff(self, repository: str, number: int, diff: str) -> dict:
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "GitHub PR diff:\n\n" + diff[:900_000]},
            ],
            "temperature": 0.1,
        }
        url = self.settings.llm_base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url += "/chat/completions"
        request = Request(url, data=json.dumps(payload).encode("utf-8"), method="POST", headers={
            "Content-Type": "application/json", "Authorization": "Bearer %s" % self.settings.llm_api_key,
        })
        try:
            with urlopen(request, timeout=self.settings.timeout_seconds) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError("LLM returned HTTP %s" % exc.code) from exc
        except URLError as exc:
            raise RuntimeError("LLM connection failed: %s" % exc.reason) from exc
        choices = response_data.get("choices") or []
        content = ((choices[0].get("message") or {}).get("content") if choices else "")
        return normalize_report(parse_json_object(str(content or "")), repository, number)


def markdown_report(report: dict) -> str:
    lines = ["## Prompt API code review", "", report.get("summary") or "No summary.", ""]
    if not report["findings"]:
        return "\n".join(lines + ["No actionable finding."])
    for item in report["findings"]:
        lines.extend([
            "### [%s] %s" % (item["severity"].upper(), item["title"]),
            "`%s:%s`" % (item["path"], item["line"]), "",
            item["explanation"], "", "**Fix:** " + item["fix"], "", "**Test:** " + item["test"], "",
        ])
    return "\n".join(lines)


class App:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = Store(settings.db_path)
        self.reviewer = PromptReviewer(settings, self.store)

    def status(self) -> dict:
        return {
            "service": "EvoPromptReview", "review_method": "one LLM API call with one fixed prompt",
            "github_token_configured": bool(self.settings.github_token),
            "webhook_secret_configured": bool(self.settings.github_webhook_secret),
            "llm_configured": self.settings.llm_ready,
            "auto_post_review": self.settings.auto_post_review,
            "public_base_url": self.settings.public_base_url,
        }


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    data = handler.rfile.read(length)
    return json.loads(data.decode("utf-8")) if data else {}


def handler_for(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "EvoPromptReview/1.0"

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def send_json(self, status: int, value: Any) -> None:
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
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
            if STATIC not in candidate.parents and candidate != STATIC:
                self.send_json(403, {"error": "forbidden"})
                return
            if not candidate.is_file():
                self.send_json(404, {"error": "not found"})
                return
            mime = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}.get(candidate.suffix, "application/octet-stream")
            body = candidate.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            try:
                if path == "/api/reviews/from-pr":
                    payload = read_json(self)
                    match = PR_URL.fullmatch(str(payload.get("pull_request_url", "")).strip())
                    if not match:
                        raise ValueError("Enter a GitHub PR URL, for example https://github.com/owner/repo/pull/42")
                    task_id = app.reviewer.enqueue(match.group("repository"), int(match.group("number")), "pr-url")
                    self.send_json(202, {"task_id": task_id, "state": "PENDING"})
                    return
                if path == "/api/github/connect":
                    payload = read_json(self)
                    repository = str(payload.get("repository", "")).strip().strip("/")
                    public_base_url = str(payload.get("public_base_url") or app.settings.public_base_url).strip().rstrip("/")
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
                        raise ValueError("Repository must use the owner/repository format")
                    parsed = urlparse(public_base_url)
                    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                        raise ValueError("Enter a valid public URL")
                    if not app.settings.github_token or not app.settings.github_webhook_secret:
                        raise ValueError("Configure the GitHub token and webhook secret first")
                    hook = app.reviewer.github.create_webhook(repository, public_base_url, app.settings.github_webhook_secret)
                    self.send_json(201, {"repository": repository, "webhook_id": hook.get("id"), "url": public_base_url + "/webhooks/github"})
                    return
                if path == "/webhooks/github":
                    body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                    secret = app.settings.github_webhook_secret.encode("utf-8")
                    signature = self.headers.get("X-Hub-Signature-256", "")
                    expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
                    if not secret or not hmac.compare_digest(signature, expected):
                        self.send_json(401, {"error": "invalid webhook signature"})
                        return
                    if not app.store.remember_delivery(self.headers.get("X-GitHub-Delivery", "")):
                        self.send_json(200, {"status": "duplicate delivery ignored"})
                        return
                    payload = json.loads(body.decode("utf-8"))
                    action = str(payload.get("action", ""))
                    pull, repository = payload.get("pull_request") or {}, payload.get("repository") or {}
                    if self.headers.get("X-GitHub-Event") != "pull_request" or action not in {"opened", "reopened", "synchronize"}:
                        self.send_json(200, {"status": "event ignored"})
                        return
                    task_id = app.reviewer.enqueue(str(repository.get("full_name", "")), int(pull.get("number", 0)), "github-webhook")
                    self.send_json(202, {"task_id": task_id, "state": "PENDING"})
                    return
                self.send_json(404, {"error": "not found"})
            except (ValueError, TypeError) as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})

    return Handler


def main() -> None:
    settings = Settings.from_env()
    app = App(settings)
    server = ThreadingHTTPServer((settings.host, settings.port), handler_for(app))
    print("EvoPromptReview: http://%s:%d" % (settings.host, settings.port))
    server.serve_forever()


if __name__ == "__main__":
    main()
