from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import verified_ssl_context


class GitHubClient:
    def __init__(self, token: str = "", timeout: int = 120):
        self.token = token
        self.timeout = timeout

    def request(self, url: str, accept: str = "application/vnd.github+json", method: str = "GET", body: bytes | None = None) -> Any:
        headers = {
            "Accept": accept,
            "User-Agent": "EvoAgent-V2/2.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=body, method=method, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout, context=verified_ssl_context()) as response:
                payload = response.read()
        except HTTPError as exc:
            raise RuntimeError("GitHub returned HTTP %s" % exc.code) from exc
        except URLError as exc:
            reason = str(exc.reason)
            if "CERTIFICATE_VERIFY_FAILED" in reason:
                raise RuntimeError(
                    "GitHub TLS certificate verification failed. Repair the local Python CA certificates; TLS verification was not disabled."
                ) from exc
            raise RuntimeError("GitHub connection failed: %s" % reason) from exc
        if "json" in accept:
            return json.loads(payload.decode("utf-8"))
        return payload.decode("utf-8")

    def pull_request(self, repository: str, number: int) -> dict:
        return self.request(f"https://api.github.com/repos/{repository}/pulls/{number}")

    def diff(self, diff_url: str) -> str:
        return self.request(diff_url, "application/vnd.github.v3.diff")

    def comment(self, repository: str, number: int, body: str) -> None:
        self.request(
            f"https://api.github.com/repos/{repository}/issues/{number}/comments",
            method="POST",
            body=json.dumps({"body": body}).encode("utf-8"),
        )
