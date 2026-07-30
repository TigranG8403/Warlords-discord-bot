from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


@dataclass(frozen=True, slots=True)
class AiClientConfig:
    base_url: str
    model: str
    api_key: str = ""
    timeout_seconds: float = 30.0
    max_response_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        base_url = self.base_url.strip().rstrip("/")
        model = self.model.strip()
        parsed = urlparse(base_url)

        if not base_url or not model:
            raise ValueError("AI base URL and model must not be empty.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("AI base URL must not contain credentials, query parameters, or fragments.")
        if parsed.scheme == "http" and parsed.hostname not in _LOOPBACK_HOSTS:
            raise ValueError("Remote AI endpoints must use HTTPS.")
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("AI base URL must be an absolute HTTP(S) URL.")
        if self.timeout_seconds <= 0:
            raise ValueError("AI timeout must be positive.")
        if self.max_response_bytes <= 0:
            raise ValueError("AI response size limit must be positive.")

        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "api_key", self.api_key.strip())

    @classmethod
    def from_env(cls) -> "AiClientConfig | None":
        base_url = os.getenv("AI_BASE_URL", "").strip()
        model = os.getenv("AI_MODEL", "").strip()
        api_key = os.getenv("AI_API_KEY", "").strip()

        if not base_url and not model and not api_key:
            return None
        if not base_url or not model:
            raise RuntimeError("AI_BASE_URL and AI_MODEL must be configured together.")

        return cls(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_seconds=float(os.getenv("AI_TIMEOUT_SECONDS", "30")),
            max_response_bytes=int(os.getenv("AI_MAX_RESPONSE_BYTES", "1000000")),
        )
