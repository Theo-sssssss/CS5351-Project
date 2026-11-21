# GitHub 接入：验证 Webhook 签名，访问 PR、文件和评论，并提供分支、提交及 Draft PR 操作。

import hashlib
import hmac
import json
import urllib.error
import urllib.request
import urllib.parse
import base64
import random
import threading
import time
from datetime import datetime, timezone
from typing import Dict


# 重算原始请求体的 HMAC-SHA256，并以恒定时间比较 GitHub 签名。
def verify_signature(secret: str, body: bytes, signature: str) -> bool:
    if not secret or not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# 封装 GitHub 资源请求、评论及修复提交操作。
class GitHubClient:
    # 保存访问令牌、单次请求超时和总尝试次数，供各 GitHub 操作复用。
    def __init__(self, token: str, timeout: int = 30, max_attempts: int = 4):
        self.token = token
        self.timeout = timeout
        self.max_attempts = max_attempts

    # 构造 GitHub API 请求头，并按配置附带授权凭据。
    def _headers(self, accept: str = "application/vnd.github+json") -> Dict[str, str]:
        headers = {"Accept": accept, "User-Agent": "EvoAgent/0.1", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        return headers

    # 下载 PR 的统一 Diff 文本，供解析器与审查器使用。
    def fetch_diff(self, url: str) -> str:
        body = self._request(
            "GET", url, accept="application/vnd.github.v3.diff", raw=True
        )
        return body.decode("utf-8", errors="replace")

    # 向目标 Issue 或 PR 创建一条评论。
    def post_comment(self, api_url: str, markdown: str) -> None:
        url = api_url.rstrip("/") + "/comments"
        request = urllib.request.Request(
            url,
            data=json.dumps({"body": markdown}).encode("utf-8"),
            headers=dict(self._headers(), **{"Content-Type": "application/json"}),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout):
            return None

    # 通过报告标记寻找已有评论，命中则更新，未命中才创建。
    def upsert_comment(self, api_url: str, markdown: str, marker: str) -> None:
        """Update this service's existing review comment instead of creating duplicates."""
        comments_url = api_url.rstrip("/") + "/comments"
        body = marker + "\n" + markdown
        for comment in self._comments(comments_url):
            if str(comment.get("body", "")).splitlines()[:1] == [marker]:
                if comment.get("body") != body:
                    endpoint = comments_url.rsplit("/issues/", 1)[0] + "/issues/comments/" + str(int(comment["id"]))
                    self._json("PATCH", endpoint, {"body": body})
                return
        self._request("POST", comments_url, {"body": body}, retry=False)

    def _comments(self, url):
        page = 1
        while True:
            values = self._json("GET", f"{url}?per_page=100&page={page}")
            yield from values
            if len(values) < 100:
                return
            page += 1

    def publish_inline_findings(self, repository, number, head_sha, findings):
        url = f"https://api.github.com/repos/{repository}/pulls/{number}/comments"
        markers = {str(comment.get("body", "")).partition("\n")[0] for comment in self._comments(url)
                   if comment.get("commit_id") == head_sha}
        posted, skipped = 0, 0
        for finding in findings:
            marker = finding["marker"]
            if marker in markers:
                posted += 1
                continue
            payload = {**{key: finding[key] for key in ("path", "line", "side")}, "commit_id": head_sha,
                       "body": marker + "\n" + finding["body"]}
            try:
                self._request("POST", url, payload, retry=False)
            except RuntimeError as exc:
                if not isinstance(exc.__cause__, urllib.error.HTTPError) or exc.__cause__.code != 422:
                    raise
                skipped += 1
                continue
            markers.add(marker)
            posted += 1
        return {"inline_posted": posted, "inline_skipped": skipped}

    # 复用请求函数并解析 JSON 返回，供仓库资源操作调用。
    def _json(self, method: str, url: str, payload=None):
        return self._request(method, url, payload)

    # 发送 GitHub HTTP 请求，处理响应类型与允许重试的错误。
    def _request(
        self, method: str, url: str, payload=None,
        accept: str = "application/vnd.github+json", raw: bool = False, retry: bool = True,
    ):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        attempts = self.max_attempts if retry else 1
        for attempt in range(1, attempts + 1):
            request = urllib.request.Request(
                url, data=data,
                headers=dict(self._headers(accept), **{"Content-Type": "application/json"}),
                method=method,
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    body = response.read()
                    if raw:
                        return body
                    return json.loads(body.decode("utf-8")) if body else {}
            except urllib.error.HTTPError as exc:
                retryable = exc.code in {429, 500, 502, 503, 504}
                if exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0":
                    retryable = True
                if not retryable or attempt >= attempts:
                    detail = exc.read(1000).decode("utf-8", errors="replace")
                    raise RuntimeError(
                        "GitHub API %s %s returned HTTP %d: %s"
                        % (method, url, exc.code, detail)
                    ) from exc
                retry_after = exc.headers.get("Retry-After")
                reset = exc.headers.get("X-RateLimit-Reset")
                if retry_after:
                    delay = float(retry_after)
                elif reset:
                    delay = max(0.0, float(reset) - time.time())
                else:
                    delay = min(2 ** (attempt - 1) + random.random(), 10)
                time.sleep(min(delay, 30))
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt >= attempts:
                    raise RuntimeError("GitHub API request failed: %s" % exc) from exc
                time.sleep(min(2 ** (attempt - 1) + random.random(), 10))

    # 读取 PR 元数据，取得分支、提交等后续修复所需信息。
    def get_pull_request(self, repository: str, number: int) -> dict:
        return self._json("GET", "https://api.github.com/repos/%s/pulls/%d" % (repository, number))

    # 读取指定引用下的文件内容及其 Git 对象标识。
    def get_file(self, repository: str, path: str, ref: str) -> dict:
        quoted = urllib.parse.quote(path, safe="/")
        result = self._json("GET", "https://api.github.com/repos/%s/contents/%s?ref=%s" % (
            repository, quoted, urllib.parse.quote(ref, safe="")
        ))
        result["decoded_content"] = base64.b64decode(result["content"]).decode("utf-8")
        return result

    # 读取仓库元信息，供访问检查和修复流程使用。
    def get_repository(self, repository: str) -> dict:
        return self._json("GET", "https://api.github.com/repos/%s" % repository)

    # 请求仓库元信息以确认当前凭据可以访问目标仓库。
    def ensure_repository_access(self, repository: str) -> None:
        result = self.get_repository(repository)
        if str(result.get("full_name", "")).lower() != repository.lower():
            raise PermissionError("GitHub installation is not authorized for this repository")

    # 从给定提交创建修复分支引用。
    def create_branch(self, repository: str, branch: str, sha: str) -> None:
        self._json("POST", "https://api.github.com/repos/%s/git/refs" % repository,
                   {"ref": "refs/heads/" + branch, "sha": sha})

    # 以文件当前 SHA 为前提提交单文件更新，避免无条件覆盖。
    def commit_file(self, repository: str, path: str, branch: str, content: str, sha: str, message: str) -> dict:
        quoted = urllib.parse.quote(path, safe="/")
        return self._json("PUT", "https://api.github.com/repos/%s/contents/%s" % (repository, quoted), {
            "message": message, "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "sha": sha, "branch": branch,
        })

    # 先创建全部文件对象和树，再创建一个提交并更新分支，保持多文件修复成组提交。
    def create_atomic_commit(
        self, repository: str, branch: str, parent_sha: str,
        files: Dict[str, str], message: str,
    ) -> dict:
        parent = self._json(
            "GET", "https://api.github.com/repos/%s/git/commits/%s"
            % (repository, parent_sha)
        )
        tree = self._json(
            "POST", "https://api.github.com/repos/%s/git/trees" % repository,
            {
                "base_tree": parent["tree"]["sha"],
                "tree": [
                    {"path": path, "mode": "100644", "type": "blob", "content": content}
                    for path, content in sorted(files.items())
                ],
            },
        )
        commit = self._json(
            "POST", "https://api.github.com/repos/%s/git/commits" % repository,
            {"message": message, "tree": tree["sha"], "parents": [parent_sha]},
        )
        self.create_branch(repository, branch, commit["sha"])
        return commit

    # 从修复分支创建 Draft PR，保留人工审阅入口。
    def create_draft_pull_request(
        self, repository: str, title: str, head: str, base: str, body: str,
    ) -> dict:
        return self._json(
            "POST", "https://api.github.com/repos/%s/pulls" % repository,
            {"title": title, "head": head, "base": base, "body": body, "draft": True},
        )

    # 下载指定引用的仓库归档，供修复前后在副本中验证。
    def download_archive(self, repository: str, ref: str) -> bytes:
        return self._request(
            "GET", "https://api.github.com/repos/%s/zipball/%s"
            % (repository, urllib.parse.quote(ref, safe="")),
            accept="application/vnd.github+json", raw=True,
        )


# 用 App 私钥换取安装级访问令牌。
class GitHubAppAuthenticator:
    _cache = {}
    _lock = threading.Lock()
    # 保存 App 标识与私钥路径，签发安装令牌时再使用。
    def __init__(self, app_id: str, private_key_path: str):
        self.app_id = app_id
        self.private_key_path = private_key_path

    # 用 GitHub App 私钥生成短期 JWT，作为安装令牌交换凭据。
    def app_jwt(self) -> str:
        try:
            import jwt
        except ImportError as exc:
            raise RuntimeError("GitHub App mode requires: pip install PyJWT[crypto]") from exc
        with open(self.private_key_path, "rb") as handle:
            key = handle.read()
        now = int(time.time())
        return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": self.app_id}, key, algorithm="RS256")

    # 使用 App 身份换取指定安装的访问令牌。
    def installation_token(self, installation_id: int) -> str:
        cache_key = (self.app_id, int(installation_id))
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and cached["expires_at"] > time.time() + 120:
                return cached["token"]
        request = urllib.request.Request(
            "https://api.github.com/app/installations/%d/access_tokens" % installation_id,
            data=b"{}", method="POST",
            headers={"Authorization": "Bearer " + self.app_jwt(), "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "EvoAgent/0.3",
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        expires = result.get("expires_at", "")
        try:
            expires_at = datetime.fromisoformat(expires.replace("Z", "+00:00")).timestamp()
        except ValueError:
            expires_at = time.time() + 3000
        with self._lock:
            self._cache[cache_key] = {"token": result["token"], "expires_at": expires_at}
        return result["token"]
