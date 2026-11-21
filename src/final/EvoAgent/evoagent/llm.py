# JSON 模型客户端：调用兼容 Chat Completions 的接口，并把耗时、Token 与错误写入执行账本。

"""Small OpenAI-compatible JSON client with auditable usage accounting."""
import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .telemetry import ExecutionLedger


class ModelResponseError(RuntimeError):
    """The provider replied, but its completion cannot be used."""

    def __init__(self, provider, code):
        self.code = code
        super().__init__(f"{provider}: {code}")


# 要求结构化 JSON 输出的兼容模型客户端。
class JsonChatClient:
    # 保存兼容模型端点、鉴权和请求超时，以及费用统计所需的供应商信息。
    def __init__(
        self, base_url: str, api_key: str, model: str,
        provider: str = "openai-compatible", timeout: int = 60,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.timeout = timeout
        self.extra_headers = dict(extra_headers or {})

    # 发送要求 JSON 输出的模型请求，解析响应并记录成功或失败的调用用量。
    def complete_json(
        self, role: str, system: str, user: str,
        ledger: Optional[ExecutionLedger] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        if max_tokens:
            payload["max_tokens"] = int(max_tokens)
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        headers.update(self.extra_headers)
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers, method="POST",
        )
        started = time.monotonic()
        usage = {}
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
            if not raw.strip():
                raise ModelResponseError(self.provider, "empty_http_response")
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeError) as exc:
                raise ModelResponseError(self.provider, "invalid_http_json") from exc
            usage = body.get("usage") or {} if isinstance(body, dict) else {}
            try:
                choice = body["choices"][0]
                content = choice["message"].get("content")
            except (KeyError, IndexError, TypeError, AttributeError) as exc:
                raise ModelResponseError(self.provider, "invalid_response_envelope") from exc
            if choice.get("finish_reason") == "length":
                raise ModelResponseError(self.provider, "output_truncated")
            if content is None or isinstance(content, str) and not content.strip():
                raise ModelResponseError(self.provider, "empty_model_content")
            try:
                result = json.loads(content)
            except (ValueError, TypeError) as exc:
                raise ModelResponseError(self.provider, "invalid_model_json") from exc
            if not isinstance(result, dict):
                raise ModelResponseError(self.provider, "invalid_model_json_root")
            if ledger:
                ledger.record_model(
                    role, self.provider, self.model, usage,
                    int((time.monotonic() - started) * 1000), True,
                )
            return result
        except ModelResponseError as exc:
            if ledger:
                ledger.record_model(role, self.provider, self.model, usage,
                                    int((time.monotonic() - started) * 1000), False, str(exc))
            raise
        except urllib.error.HTTPError as exc:
            message = "%s API returned HTTP %d" % (self.provider, exc.code)
        except (urllib.error.URLError, socket.timeout, ValueError, KeyError,
                IndexError, TypeError, json.JSONDecodeError) as exc:
            message = "%s JSON request failed: %s" % (self.provider, exc)
        if ledger:
            ledger.record_model(
                role, self.provider, self.model, {},
                int((time.monotonic() - started) * 1000), False, message,
            )
        raise RuntimeError(message)
