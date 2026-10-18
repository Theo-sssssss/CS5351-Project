from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import verified_ssl_context


def parse_json_object(text: str) -> dict:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("LLM did not return a JSON object")
        parsed = json.loads(value[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM response root must be an object")
    return parsed


@dataclass
class LLMResult:
    value: dict
    input_tokens: int = 0
    output_tokens: int = 0


class ChatCompletionsClient:
    def __init__(self, url: str, api_key: str, model: str, timeout: int = 120):
        self.url = url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete_json(self, system_prompt: str, user_prompt: str) -> LLMResult:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")
        request = Request(
            self.url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key},
        )
        try:
            with urlopen(request, timeout=self.timeout, context=verified_ssl_context()) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            messages = {
                401: "LLM authentication failed (HTTP 401)",
                403: "LLM access forbidden (HTTP 403)",
                404: "LLM endpoint or model not found (HTTP 404)",
                405: "LLM endpoint rejected POST; configure the exact Chat Completions URL (HTTP 405)",
                429: "LLM rate limit reached (HTTP 429)",
            }
            raise RuntimeError(messages.get(exc.code, f"LLM returned HTTP {exc.code}")) from exc
        except URLError as exc:
            raise RuntimeError("LLM connection failed: %s" % exc.reason) from exc
        choices = payload.get("choices") or []
        content: Any = ((choices[0].get("message") or {}).get("content") if choices else "")
        usage = payload.get("usage") or {}
        return LLMResult(
            parse_json_object(str(content or "")),
            int(usage.get("prompt_tokens") or 0),
            int(usage.get("completion_tokens") or 0),
        )
