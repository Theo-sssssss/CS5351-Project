# HTTP 接口与静态页面入口：解析请求、校验身份和权限，再调用 ReviewService。
# 用户请求按租户访问数据；GitHub Webhook 使用独立的签名校验流程。

import hashlib
import json
import mimetypes
import os
import re
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict

from .config import Settings
from .auth import Principal
from .batch_review import ReviewConflict
from .github import verify_signature
from .github_review import REPOSITORY
from .metrics import metrics
from .modes import public_taxonomy, resolve_mode
from .report import to_markdown
from .service import ReviewService


TASK = re.compile(r"^/v1/tasks/([0-9a-f-]+)$")
REPORT = re.compile(r"^/v1/tasks/([0-9a-f-]+)/report$")
FIX = re.compile(r"^/v1/tasks/([0-9a-f-]+)/fix$")
FEEDBACK = re.compile(r"^/v1/tasks/([0-9a-f-]+)/feedback$")
CANCEL = re.compile(r"^/v1/tasks/([0-9a-f-]+)/cancel$")
RESUME = re.compile(r"^/v1/tasks/([0-9a-f-]+)/resume$")
ACCEPT = re.compile(r"^/v1/tasks/([0-9a-f-]+)/accept$")
TASK_WORKBENCH = re.compile(r"^/v1/tasks/([0-9a-f-]+)/(progress|workbench|diff)$")
FINDING = re.compile(r"^/v1/tasks/([0-9a-f-]+)/findings/([0-9a-f]{32})$")
EVOLUTION_JOB = re.compile(r"^/v1/evolution/jobs/([0-9a-f-]+)$")
VERSION_CATALOG = re.compile(r"^/v1/versions/(prompt|skill)/([a-z0-9_-]+)(?:/(\d+))?$")
VERSION_PUBLISH = re.compile(r"^/v1/versions/(prompt|skill)/([a-z0-9_-]+)/(\d+)/publish$")
ROLLBACK = re.compile(r"^/v1/skills/([A-Za-z0-9_-]+)/versions/(\d+)/activate$")
SKILL_ARTIFACT_VERSIONS = re.compile(r"^/v1/skill-evolution/([a-z0-9_-]+)/versions$")
SKILL_ARTIFACT_ACTIVATE = re.compile(
    r"^/v1/skill-evolution/([a-z0-9_-]+)/versions/(\d+)/activate$"
)
WEB_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))


# 基于标准库的 HTTP 请求处理器，负责路由和接口边界校验。
class ApiHandler(BaseHTTPRequestHandler):
    service: ReviewService
    settings: Settings
    server_version = "EvoAgent/0.3"

    # 将客户端地址与格式化后的请求日志输出到标准输出，便于容器收集。
    def log_message(self, fmt: str, *args: Any) -> None:
        print("%s - %s" % (self.address_string(), fmt % args))

    # 写入状态码、内容类型及通用响应头。
    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.end_headers()

    # 按配置解析身份并要求所需权限，返回当前请求的租户与角色。
    def _principal(self, permission: str = "read") -> Principal:
        if not self.settings.auth_required:
            return Principal(
                "local", "local-development", self.settings.default_tenant_id, "admin"
            )
        principal = self.service.auth.authenticate(self.headers.get("Authorization", ""))
        self.service.auth.require(principal, (permission,))
        return principal

    # 捕获认证错误并发送对应响应，避免各路由重复处理未登录情况。
    def _authenticate_or_send(self, permission: str = "read"):
        try:
            return self._principal(permission)
        except PermissionError as exc:
            self._send_json(401, {"error": str(exc)})
            return None

    # 以 UTF-8 输出 JSON 响应，并设置正确的内容长度。
    def _send_json(self, status: int, value: Dict[str, Any]) -> None:
        body = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    # 输出指定内容类型的文本，供报告和指标端点使用。
    def _send_text(self, status: int, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        body = text.encode("utf-8")
        self._headers(status, content_type, len(body))
        self.wfile.write(body)

    # 读取 Web 静态文件并根据扩展名设置响应类型，缺失时返回错误。
    def _serve_file(self, filename: str) -> None:
        path = os.path.abspath(os.path.join(WEB_ROOT, filename))
        if not path.startswith(WEB_ROOT + os.sep) and path != WEB_ROOT:
            self._send_json(404, {"error": "not found"})
            return
        try:
            with open(path, "rb") as handle:
                body = handle.read()
        except OSError:
            self._send_json(404, {"error": "not found"})
            return
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self._headers(200, content_type, len(body))
        self.wfile.write(body)

    # 按 Content-Length 读取请求体，并检查配置的大小限制。
    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("invalid Content-Length")
        limit = self.settings.max_diff_bytes + 256 * 1024
        if length <= 0 or length > limit:
            raise ValueError("request body is empty or too large")
        return self.rfile.read(length)

    # 把请求体解析成 JSON 对象，拒绝格式或顶层类型不符的输入。
    @staticmethod
    def _read_json(body: bytes) -> Dict[str, Any]:
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("request body must be valid UTF-8 JSON")
        if not isinstance(value, dict):
            raise ValueError("JSON root must be an object")
        return value

    # 分发查询和静态页面请求；业务查询按身份限定租户，管理接口另查权限。
    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)
        if path == "/":
            self._serve_file("index.html")
            return
        if path == "/assets/app.css":
            self._serve_file("app.css")
            return
        if path == "/assets/login.css":
            self._serve_file("login.css")
            return
        if path == "/assets/app.js":
            self._serve_file("app.js")
            return
        if path == "/health":
            mode = resolve_mode(
                None, bool(self.service.llm_config)
            )
            self._send_json(200, {"status": "ok", "reviewer": self.service.reviewer.name,
                                  "runtime": self.service.harness.name,
                                  "queue": self.service.queue.backend,
                                  "llm_provider": self.service.llm_config.get("provider", "local"),
                                  "llm_model": self.service.llm_config.get("model", ""),
                                  "run_mode": mode.to_dict(),
                                  "taxonomy": public_taxonomy()})
            return
        principal = self._authenticate_or_send("read")
        if principal is None:
            return
        if path == "/metrics":
            self._send_text(200, metrics.prometheus(), "text/plain; version=0.0.4; charset=utf-8")
            return
        if path == "/api/dashboard":
            mode = resolve_mode(
                None, bool(self.service.llm_config)
            )
            self._send_json(200, {"stats": self.service.store.dashboard_stats(principal.tenant_id),
                                  "tasks": self.service.store.list_tasks(10, principal.tenant_id),
                                  "queue": self.service.queue.backend,
                                  "orchestrator": self.service.reviewer.name,
                                  "llm": {
                                      "enabled": bool(self.service.llm_config),
                                      "provider": self.service.llm_config.get("provider", "local"),
                                      "model": self.service.llm_config.get("model", ""),
                                  },
                                  "run_mode": mode.to_dict(),
                                  "taxonomy": public_taxonomy()})
            return
        if path == "/api/tasks":
            try:
                if {"repository", "pull_request", "state", "page"} & query.keys():
                    pr = query.get("pull_request", [""])[0]
                    result = self.service.workbench.tasks(
                        principal.tenant_id, query.get("repository", [""])[0], int(pr) if pr else None,
                        query.get("state", [""])[0], int(query.get("page", [1])[0]),
                    )
                else:
                    result = {"tasks": self.service.store.list_tasks(int(query.get("limit", [50])[0]), principal.tenant_id)}
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, result)
            return
        if path == "/v1/review-settings":
            repository = query.get("repository", [""])[0].lower()
            if not REPOSITORY.fullmatch(repository):
                self._send_json(400, {"error": "Invalid repository name"})
            elif not principal.can("manage") or not self.service.store.repository_allowed(principal.tenant_id, repository):
                self._send_json(403, {"error": "permission denied"})
            else:
                self._send_json(200, {"publication": self.service.github_review.publication_policy(principal.tenant_id, repository)})
            return
        if path == "/api/skills":
            self._send_json(200, {
                "skills": self.service.list_skills(principal.tenant_id),
                "llm": {
                    "enabled": bool(self.service.llm_config),
                    "provider": self.service.llm_config.get("provider", "local"),
                    "model": self.service.llm_config.get("model", ""),
                },
            })
            return
        if path == "/api/failures":
            if not principal.can("audit"):
                self._send_json(403, {"error": "permission denied"})
                return
            self._send_json(200, {"cases": self.service.store.list_failure_cases(
                False, 100, principal.tenant_id
            )})
            return
        if path == "/api/audit":
            if not principal.can("audit"):
                self._send_json(403, {"error": "permission denied"})
                return
            self._send_json(200, {"events": self.service.store.list_audit(
                principal.tenant_id, int(query.get("limit", [100])[0])
            )})
            return
        if path == "/api/alerts":
            self._send_json(200, {"alerts": self.service.store.list_alerts(principal.tenant_id)})
            return
        if path == "/api/deployments/llm-review":
            self._send_json(200, {"deployment": self.service.store.get_deployment(
                principal.tenant_id, "llm-review"
            )})
            return
        if path == "/api/queue/dead-letters":
            if not principal.can("manage"):
                self._send_json(403, {"error": "permission denied"})
                return
            self._send_json(200, {"messages": self.service.queue.dead_letters(
                int(query.get("limit", [100])[0])
            )})
            return
        if path == "/v1/evaluation/cases":
            split = query.get("split", ["validation"])[0]
            if split == "holdout":
                self._send_json(403, {"error": "holdout cases are not exposed through the API"})
                return
            self._send_json(200, {
                "cases": self.service.store.list_evaluation_cases(split, True, 100)
            })
            return
        if path == "/v1/evolution/runs":
            if not principal.can("manage") or principal.tenant_id != self.settings.default_tenant_id:
                self._send_json(403, {"error": "permission denied"})
                return
            self._send_json(200, {
                "runs": self.service.store.list_evolution_runs(int(query.get("limit", [50])[0]))
            })
            return
        if path == "/v1/evolution/status":
            status = self.service.evolution.status()
            status["provider"] = self.service.llm_config.get("provider", "local")
            status["model"] = self.service.llm_config.get("model", "")
            self._send_json(200, status)
            return
        match = VERSION_CATALOG.match(path)
        if match:
            if not principal.can("manage"):
                self._send_json(403, {"error": "permission denied"})
                return
            try:
                if match[3]:
                    result = self.service.version_detail(match[1], match[2], int(match[3]), principal.tenant_id)
                else:
                    result = self.service.version_catalog(match[1], match[2], principal.tenant_id)
                    if query.get("summary", [""])[0] == "1":
                        result["versions"] = [{key: version.get(key) for key in ("version", "active", "created_at", "release_state")}
                                              for version in result["versions"]]
            except PermissionError as exc:
                self._send_json(403, {"error": str(exc)})
                return
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except LookupError as exc:
                self._send_json(404, {"error": str(exc)})
                return
            self._send_json(200, result)
            return
        if path == "/v1/evolution/jobs":
            if not principal.can("manage"):
                self._send_json(403, {"error": "permission denied"})
                return
            kind, name = query.get("kind", ["prompt"])[0], query.get("name", ["llm-review"])[0]
            try:
                self.service._version_scope(kind, name, principal.tenant_id)
            except (PermissionError, ValueError) as exc:
                self._send_json(403 if isinstance(exc, PermissionError) else 400, {"error": str(exc)})
                return
            self._send_json(200, {"jobs": self.service.store.evolution_jobs(principal.tenant_id, kind, name)})
            return
        match = EVOLUTION_JOB.match(path)
        if match:
            if not principal.can("manage"):
                self._send_json(403, {"error": "permission denied"})
                return
            job = self.service.evolution_job(match[1], principal.tenant_id)
            self._send_json(200 if job else 404, job or {"error": "job not found"})
            return
        if path == "/v1/skill-evolution/status":
            if not principal.can("manage"):
                self._send_json(403, {"error": "permission denied"})
                return
            skill_name = query.get("skill_name", ["evolved-review"])[0]
            self._send_json(200, self.service.skill_evolution.status(
                skill_name, principal.tenant_id
            ))
            return
        if path == "/v1/skill-evolution/runs":
            if not principal.can("manage"):
                self._send_json(403, {"error": "permission denied"})
                return
            self._send_json(200, {"runs": self.service.store.list_skill_evolution_runs(
                int(query.get("limit", [50])[0]), principal.tenant_id
            )})
            return
        match = SKILL_ARTIFACT_VERSIONS.match(path)
        if match:
            if not principal.can("manage"):
                self._send_json(403, {"error": "permission denied"})
                return
            self._send_json(200, {"versions": self.service.store.list_skill_artifact_versions(
                match.group(1), principal.tenant_id
            )})
            return
        if path == "/github/install":
            if not self.settings.github_app_slug:
                self._send_json(503, {"error": "EVOAGENT_GITHUB_APP_SLUG is not configured"})
                return
            self.send_response(302)
            self.send_header("Location", "https://github.com/apps/%s/installations/new" % self.settings.github_app_slug)
            self.end_headers()
            return
        if path == "/github/setup":
            try:
                installation_id = int(query.get("installation_id", [""])[0])
            except ValueError:
                self._send_json(400, {"error": "missing installation_id"})
                return
            self.service.store.save_installation(installation_id, query.get("account", ["github-app"])[0])
            self.send_response(302)
            self.send_header("Location", "/#github")
            self.end_headers()
            return
        report_match = REPORT.match(path)
        workbench_match = TASK_WORKBENCH.match(path)
        if workbench_match:
            workbench = self.service.workbench
            try:
                task = workbench.header(workbench_match[1], principal.tenant_id)
                section = workbench_match[2]
                if section == "progress":
                    result = workbench.progress(task, principal.can("review"), principal.can("fix"))
                elif section == "workbench":
                    result = workbench.content(task, principal.can("review"))
                else:
                    result = workbench.diff(task, query.get("file", [""])[0], int(query.get("offset", [0])[0]),
                                            query.get("side", ["new"])[0], int(query.get("line", [0])[0]))
            except LookupError as exc:
                self._send_json(404, {"error": str(exc)})
                return
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(200, result)
            return
        task_match = TASK.match(path)
        feedback_match = FEEDBACK.match(path)
        if feedback_match:
            if not principal.can("review"):
                self._send_json(403, {"error": "permission denied"})
                return
            task = self.service.store.get(feedback_match.group(1), principal.tenant_id)
            if not task:
                self._send_json(404, {"error": "task not found"})
                return
            self._send_json(200, {"cases": self.service.store.list_task_failure_cases(
                feedback_match.group(1), principal.tenant_id
            )})
            return
        if report_match:
            task = self.service.store.get(report_match.group(1), principal.tenant_id)
            if not task or not self.service.store.repository_allowed(principal.tenant_id, task["repository"]):
                self._send_json(404, {"error": "task or report not found"})
                return
            task = self.service.batch_review.details(task, False)
            report = task.get("report") or task.get("partial_report")
            if not report:
                self._send_json(404, {"error": "task or report not found"})
                return
            self._send_text(200, to_markdown(report), "text/markdown; charset=utf-8")
            return
        if task_match:
            task = self.service.store.get(task_match.group(1), principal.tenant_id)
            if not task or task["input"].get("job_type") or not self.service.store.repository_allowed(
                principal.tenant_id, task["repository"]
            ):
                self._send_json(404, {"error": "task not found"})
                return
            self._send_json(200, self.service.batch_review.details(task, principal.can("review")))
            return
        self._send_json(404, {"error": "not found"})

    # 分发登录、审查、反馈、修复和管理请求，将校验异常转换为 HTTP 响应。
    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)
        try:
            body = self._read_body()
            if path == "/v1/auth/login":
                if not self.settings.auth_required:
                    self._send_json(409, {"error": "authentication is disabled"})
                    return
                payload = self._read_json(body)
                try:
                    result = self.service.auth.login(
                        str(payload.get("username", "")), str(payload.get("password", "")),
                        str(payload.get("tenant_id", "")),
                    )
                except PermissionError as exc:
                    self._send_json(401, {"error": str(exc)})
                    return
                self._send_json(200, result)
                return
            if path == "/v1/reviews":
                principal = self._principal("review")
                payload = self._read_json(body)
                pr = payload.get("pull_request")
                if pr is not None and not isinstance(pr, int):
                    raise ValueError("pull_request must be an integer")
                args = (str(payload.get("repository", "")), str(payload.get("diff", "")), pr)
                enabled_agents = payload.get("enabled_agents")
                if enabled_agents is not None and (
                    not isinstance(enabled_agents, list)
                    or not all(isinstance(item, str) for item in enabled_agents)
                ):
                    raise ValueError("enabled_agents must be an array of role names")
                enabled_skills = payload.get("enabled_skills")
                if enabled_skills is not None and (
                    not isinstance(enabled_skills, list)
                    or not all(isinstance(item, str) for item in enabled_skills)
                ):
                    raise ValueError("enabled_skills must be an array of Agent Skill names")
                options = {
                    "tenant_id": principal.tenant_id,
                    "mode": str(payload.get("mode", "")),
                    "repository_root": str(payload.get("repository_root", "")),
                    "enabled_agents": enabled_agents,
                    "enabled_skills": enabled_skills,
                }
                if query.get("async", ["false"])[0].lower() == "true":
                    result = self.service.enqueue_review(*args, **options)
                    self._send_json(202, result)
                else:
                    self._send_json(201, self.service.create_review(
                        *args, **options
                    ))
                self.service.store.audit(
                    principal.tenant_id, principal.username, "review.create",
                    str(payload.get("repository", "")), {
                        "async": query.get("async", ["false"])[0],
                        "mode": str(payload.get("mode", "")),
                    },
                )
                return
            if path == "/v1/reviews/github":
                principal = self._principal("review")
                payload = self._read_json(body)
                result = self.service.github_review.enqueue_url(payload.get("pr_url"), principal.tenant_id)
                self.service.store.audit(principal.tenant_id, principal.username, "review.github.create",
                                         result["task_id"], {"duplicate": result["duplicate"]})
                self._send_json(202, result)
                return
            if path == "/v1/review-settings":
                principal = self._principal("manage")
                payload = self._read_json(body)
                repository = str(payload.get("repository", "")).lower()
                publication = payload.get("publication")
                if (not REPOSITORY.fullmatch(repository) or not isinstance(publication, str)
                        or publication not in {"off", "summary", "inline"}):
                    raise ValueError("Invalid repository or publication mode")
                self.service._authorize_repository(principal.tenant_id, repository)
                self.service.store.save_repository_publication(principal.tenant_id, repository, publication)
                self.service.store.audit(principal.tenant_id, principal.username, "review.publication", repository,
                                         {"publication": publication})
                self._send_json(200, {"publication": publication})
                return
            match = FINDING.match(path)
            if match:
                principal = self._principal("review")
                payload = self._read_json(body)
                workbench = self.service.workbench
                task = workbench.header(match[1], principal.tenant_id)
                self._send_json(200, workbench.set_finding(task, match[2], payload.get("state"),
                                                          payload.get("note", ""), principal.username))
                return
            if path == "/webhooks/github":
                if self.headers.get("X-GitHub-Event", "") != "pull_request":
                    self._send_json(202, {"ignored": True, "reason": "unsupported GitHub event"})
                    return
                if not self.settings.github_webhook_secret:
                    self._send_json(503, {"error": "GitHub webhook secret is not configured"})
                    return
                if not verify_signature(self.settings.github_webhook_secret, body,
                                        self.headers.get("X-Hub-Signature-256", "")):
                    self._send_json(401, {"error": "invalid webhook signature"})
                    return
                payload = self._read_json(body)
                updated_at = (payload.get("pull_request") or {}).get("updated_at")
                if updated_at:
                    try:
                        event_time = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                    except ValueError:
                        raise ValueError("invalid pull_request.updated_at")
                    age = abs((datetime.now(timezone.utc) - event_time).total_seconds())
                    if age > self.settings.webhook_max_age_seconds:
                        self._send_json(409, {"error": "webhook is outside the replay window"})
                        return
                delivery_id = self.headers.get("X-GitHub-Delivery", "")
                digest = hashlib.sha256(body).hexdigest()
                self._send_json(202, self.service.handle_github_pull_request(
                    payload, delivery_id, digest
                ))
                return
            match = FIX.match(path)
            if match:
                principal = self._principal("fix")
                payload = self._read_json(body)
                installation_id = payload.get("installation_id")
                if installation_id is not None and not isinstance(installation_id, int):
                    raise ValueError("installation_id must be an integer")
                result = self.service.create_fix(
                    match.group(1), installation_id, principal.tenant_id
                )
                self.service.store.audit(
                    principal.tenant_id, principal.username, "repair.create",
                    match.group(1), {"branch": result.get("branch")},
                )
                self._send_json(201, result)
                return
            match = FEEDBACK.match(path)
            if match:
                principal = self._principal("review")
                payload = self._read_json(body)
                result = self.service.record_feedback(
                    match.group(1), str(payload.get("category", "")), payload.get("finding"),
                    str(payload.get("note", "")), principal.tenant_id,
                    str(payload.get("skill_name") or "llm-review"),
                )
                self.service.store.audit(
                    principal.tenant_id, principal.username, "feedback.record", match.group(1),
                    {"category": result["category"], "skill_name": result["skill_name"]},
                )
                self._send_json(201, result)
                return
            match = CANCEL.match(path)
            if match:
                principal = self._principal("review")
                ok = self.service.cancel_task(match.group(1), principal.tenant_id)
                self.service.store.audit(
                    principal.tenant_id, principal.username, "task.cancel", match.group(1)
                )
                self._send_json(202 if ok else 404, {"cancel_requested": ok})
                return
            match = RESUME.match(path)
            if match:
                principal = self._principal("review")
                payload = self._read_json(body) if body else {}
                result = self.service.resume_task(match.group(1), principal.tenant_id, payload.get("additional_tokens", 0))
                self.service.store.audit(
                    principal.tenant_id, principal.username, "task.resume", match.group(1)
                )
                self._send_json(202, result)
                return
            match = ACCEPT.match(path)
            if match:
                principal = self._principal("review")
                payload = self._read_json(body)
                result = self.service.accept_review(match[1], principal.tenant_id, principal.username,
                                                    payload.get("report_revision"))
                self._send_json(200, {"confirmation": result})
                return
            match = VERSION_PUBLISH.match(path)
            if match:
                principal = self._principal("manage")
                payload = self._read_json(body) if body else {}
                result = self.service.publish_version(match[1], match[2], int(match[3]), principal.tenant_id,
                                                      principal.username, payload.get("canary_percent", 0))
                self._send_json(200, result)
                return
            if path == "/v1/skills/reload":
                principal = self._principal("manage")
                self._send_json(200, {"skills": self.service.reload_skills(),
                                      "note": "New tasks now use the reloaded skill set."})
                return
            if path == "/v1/deployments/llm-review":
                principal = self._principal("manage")
                payload = self._read_json(body)
                if type(payload.get("canary_percent")) is not int or not 1 <= payload["canary_percent"] <= 100:
                    raise ValueError("Use a canary_percent between 1 and 100 for deployment. Activate stable from the version workbench.")
                result = self.service.publish_version("prompt", "llm-review", payload.get("candidate_version"),
                                                      principal.tenant_id, principal.username, payload.get("canary_percent", 0))
                self.service.store.audit(
                    principal.tenant_id, principal.username, "deployment.configure",
                    "llm-review", payload,
                )
                self._send_json(201, result["deployment"])
                return
            if path == "/v1/queue/dead-letters/replay":
                principal = self._principal("manage")
                payload = self._read_json(body)
                ok = self.service.queue.replay_dead_letter(
                    str(payload.get("message_id", ""))
                )
                self._send_json(202 if ok else 404, {"replayed": ok})
                return
            if path == "/v1/evaluation/cases":
                self._principal("manage")
                payload = self._read_json(body)
                result = self.service.evolution.add_evaluation_case(
                    str(payload.get("name", "")),
                    str(payload.get("diff", "")),
                    payload.get("expected_findings", []),
                    str(payload.get("split", "validation")),
                    "api",
                )
                self._send_json(201, result)
                return
            if path == "/v1/evolution/auto":
                principal = self._principal("manage")
                payload = self._read_json(body)
                self._evaluate_response("prompt", str(payload.get("skill_name", "llm-review")),
                                        principal, {"automatic": True}, query)
                return
            if path == "/v1/evolution/propose":
                principal = self._principal("manage")
                payload = self._read_json(body)
                self._evaluate_response("prompt", str(payload.get("skill_name", "llm-review")),
                                        principal, {"prompt": str(payload.get("prompt", ""))}, query)
                return
            if path == "/v1/skill-evolution/auto":
                principal = self._principal("manage")
                payload = self._read_json(body)
                self._evaluate_response("skill", str(payload.get("skill_name", "evolved-review")),
                                        principal, {"automatic": True}, query)
                return
            if path == "/v1/skill-evolution/propose":
                principal = self._principal("manage")
                payload = self._read_json(body)
                artifact = payload.get("artifact")
                if artifact is None and "skill_md" in payload:
                    artifact = {
                        "name": str(payload.get("skill_name", "")),
                        "skill_md": payload.get("skill_md"),
                        "supporting_files": payload.get("supporting_files") or {},
                    }
                self._evaluate_response("skill", str(payload.get("skill_name", "")),
                                        principal, {"artifact": artifact}, query)
                return
            match = SKILL_ARTIFACT_ACTIVATE.match(path)
            if match:
                principal = self._principal("manage")
                self.service.publish_version("skill", match[1], int(match[2]), principal.tenant_id, principal.username)
                self._send_json(200, {"activated": True})
                return
            match = ROLLBACK.match(path)
            if match:
                principal = self._principal("manage")
                self.service.publish_version("prompt", match[1], int(match[2]), principal.tenant_id, principal.username)
                self._send_json(200, {"activated": True})
                return
            self._send_json(404, {"error": "not found"})
        except ReviewConflict as exc:
            self._send_json(409, {"error": str(exc)})
        except LookupError as exc:
            self._send_json(404, {"error": str(exc)})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except PermissionError as exc:
            self._send_json(403, {"error": str(exc)})
        except Exception as exc:
            metrics.inc("http_errors_total")
            self._send_json(500, {"error": "operation failed", "detail": str(exc)})

    def _evaluate_response(self, kind, name, principal, options, query):
        if query.get("async", ["false"])[0].lower() == "true":
            result = self.service.queue_evolution(kind, name, principal.tenant_id, principal.username, options)
            self._send_json(202, result)
        else:
            result = self.service.evaluate_version(kind, name, principal.tenant_id, options)
            self.service.store.audit(principal.tenant_id, principal.username, f"{kind}.evaluate", name,
                                     {"decision": result["decision"], "run_id": result.get("run_id")})
            self._send_json(201, result)


# 从环境构建服务并绑定请求处理器，启动线程化 HTTP 服务器。
def run() -> None:
    settings = Settings.from_env()
    service = ReviewService(settings)
    handler = type("ConfiguredApiHandler", (ApiHandler,), {"service": service, "settings": settings})
    server = ThreadingHTTPServer((settings.host, settings.port), handler)
    print("EvoAgent dashboard: http://%s:%d" % (settings.host, settings.port))
    print("Persistence: %s | Queue: %s | Orchestrator: %s" % (
        "postgresql" if settings.database_url else "sqlite", service.queue.backend, service.reviewer.name
    ))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.queue.close(wait=False)
        server.server_close()
