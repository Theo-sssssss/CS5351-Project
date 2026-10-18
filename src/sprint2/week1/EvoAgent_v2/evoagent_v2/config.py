from __future__ import annotations

import os
import ssl
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CA_CANDIDATES = (
    "/etc/ssl/cert.pem",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/opt/homebrew/etc/ca-certificates/cert.pem",
)


def verified_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if context.get_ca_certs():
        return context
    for candidate in CA_CANDIDATES:
        if Path(candidate).is_file():
            return ssl.create_default_context(cafile=candidate)
    return context


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env(name: str, default: str = "", *legacy: str) -> str:
    for key in (name, *legacy):
        value = os.getenv(key)
        if value is not None:
            return value.strip()
    return default


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    db_path: str
    github_token: str
    github_webhook_secret: str
    auto_post_review: bool
    llm_url: str
    llm_api_key: str
    llm_model: str
    timeout_seconds: int
    max_request_bytes: int
    max_diff_bytes: int
    worker_count: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT / ".env")
        exact_url = env("EVOAGENT_V2_LLM_CHAT_COMPLETIONS_URL")
        base_url = env(
            "EVOAGENT_V2_LLM_BASE_URL", "", "PROMPT_REVIEW_LLM_BASE_URL", "EVOAGENT_LLM_BASE_URL"
        )
        llm_url = exact_url or cls.normalize_chat_url(base_url)
        return cls(
            host=env("EVOAGENT_V2_HOST", "127.0.0.1"),
            port=int(env("EVOAGENT_V2_PORT", "8083")),
            db_path=env("EVOAGENT_V2_DB_PATH", str(ROOT / "evoagent_v2.db")),
            github_token=env("EVOAGENT_V2_GITHUB_TOKEN", "", "PROMPT_REVIEW_GITHUB_TOKEN", "EVOAGENT_GITHUB_TOKEN"),
            github_webhook_secret=env(
                "EVOAGENT_V2_GITHUB_WEBHOOK_SECRET", "", "PROMPT_REVIEW_GITHUB_WEBHOOK_SECRET", "EVOAGENT_GITHUB_WEBHOOK_SECRET"
            ),
            auto_post_review=env("EVOAGENT_V2_AUTO_POST_REVIEW", "false").lower() == "true",
            llm_url=llm_url,
            llm_api_key=env("EVOAGENT_V2_LLM_API_KEY", "", "PROMPT_REVIEW_LLM_API_KEY", "EVOAGENT_LLM_API_KEY"),
            llm_model=env("EVOAGENT_V2_LLM_MODEL", "", "PROMPT_REVIEW_LLM_MODEL", "EVOAGENT_LLM_MODEL"),
            timeout_seconds=int(env("EVOAGENT_V2_TIMEOUT_SECONDS", "120")),
            max_request_bytes=int(env("EVOAGENT_V2_MAX_REQUEST_BYTES", "1048576")),
            max_diff_bytes=int(env("EVOAGENT_V2_MAX_DIFF_BYTES", "900000")),
            worker_count=max(1, int(env("EVOAGENT_V2_WORKER_COUNT", "2"))),
        )

    @staticmethod
    def normalize_chat_url(base_url: str) -> str:
        value = base_url.rstrip("/")
        if not value:
            return ""
        if value.endswith("/chat/completions"):
            return value
        return value + "/chat/completions"

    @property
    def llm_ready(self) -> bool:
        return bool(self.llm_url and self.llm_api_key and self.llm_model)

    @staticmethod
    def tls_diagnostics() -> dict:
        try:
            context = verified_ssl_context()
            return {"ready": bool(context.get_ca_certs()), "ca_certificates": len(context.get_ca_certs())}
        except Exception as exc:
            return {"ready": False, "error": str(exc)[:240]}
