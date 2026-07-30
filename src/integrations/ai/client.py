from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass
import json
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import AiClientConfig


AiRole = Literal["system", "user", "assistant"]
Transport = Callable[[Request, float, int], bytes]


class AiClientError(RuntimeError):
    """Raised when an AI provider cannot return a valid completion."""


@dataclass(frozen=True, slots=True)
class AiMessage:
    role: AiRole
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"system", "user", "assistant"}:
            raise ValueError(f"Unsupported AI message role: {self.role!r}.")
        if not self.content.strip():
            raise ValueError("AI message content must not be empty.")


class OpenAiCompatibleClient:
    def __init__(
        self,
        config: AiClientConfig,
        *,
        transport: Transport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport or _default_transport

    async def complete(
        self,
        messages: Iterable[AiMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return await asyncio.to_thread(
            self.complete_sync,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def complete_sync(
        self,
        messages: Iterable[AiMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str:
        serialized_messages = [
            {"role": message.role, "content": message.content}
            for message in messages
        ]
        if not serialized_messages:
            raise ValueError("At least one AI message is required.")
        if temperature is not None and not 0 <= temperature <= 2:
            raise ValueError("AI temperature must be between 0 and 2.")
        if max_tokens is not None and max_tokens <= 0:
            raise ValueError("AI max_tokens must be positive.")

        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": serialized_messages,
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        request = Request(
            self._endpoint(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )

        try:
            response_body = self._transport(
                request,
                self._config.timeout_seconds,
                self._config.max_response_bytes,
            )
            response = json.loads(response_body.decode("utf-8"))
            content = response["choices"][0]["message"]["content"]
        except AiClientError:
            raise
        except (IndexError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AiClientError("AI provider returned an invalid completion response.") from error

        if not isinstance(content, str) or not content.strip():
            raise AiClientError("AI provider returned an empty completion.")
        return content.strip()

    async def complete_json(
        self,
        messages: Iterable[AiMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        content = await asyncio.to_thread(
            self.complete_sync,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        try:
            value = json.loads(content)
        except json.JSONDecodeError as error:
            raise AiClientError("AI provider returned invalid JSON content.") from error
        if not isinstance(value, dict):
            raise AiClientError("AI provider JSON response must be an object.")
        return value

    def _endpoint(self) -> str:
        if self._config.base_url.endswith("/chat/completions"):
            return self._config.base_url
        return f"{self._config.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "WarlordsBot/1",
        }
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"
        return headers


def _default_transport(request: Request, timeout_seconds: float, max_response_bytes: int) -> bytes:
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_response_bytes:
                raise AiClientError("AI provider response exceeds the configured size limit.")
            body = response.read(max_response_bytes + 1)
    except HTTPError as error:
        raise AiClientError(f"AI provider rejected the request with HTTP {error.code}.") from error
    except (TimeoutError, URLError) as error:
        raise AiClientError("AI provider request failed.") from error

    if len(body) > max_response_bytes:
        raise AiClientError("AI provider response exceeds the configured size limit.")
    return body
