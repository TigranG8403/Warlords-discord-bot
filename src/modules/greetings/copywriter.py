from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import logging
import secrets
from typing import Protocol

from integrations.ai import AiClientError, AiMessage

from .content import fallback_line, sanitize_generated_line, theme_for


logger = logging.getLogger(__name__)


class GreetingAiClient(Protocol):
    async def complete(
        self,
        messages,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str: ...


class GreetingCopywriter:
    def __init__(
        self,
        ai_client: GreetingAiClient | None,
        *,
        timeout_seconds: float = 6.5,
        max_concurrent_requests: int = 2,
    ) -> None:
        self._ai_client = ai_client
        self._timeout_seconds = timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)

    async def create_line(self, *, member_id: int, current_time: dt.datetime) -> str:
        fallback = fallback_line(member_id)
        if self._ai_client is None or self._semaphore.locked():
            return fallback

        marker = _variant_marker(member_id, current_time)
        messages = (
            AiMessage(
                "system",
                (
                    "Напиши одну короткую приветственную реплику для нового участника "
                    "средневекового военно-политического RP-сообщества Warlords. "
                    "Нужен живой современный русский язык с лёгкой исторической атмосферой, "
                    "бытовой деталью, спокойной иронией или ненавязчивой отсылкой. "
                    "Не используй фэнтезийный пафос, пророчества, оценку личности, прямые "
                    "исторические утверждения, эмодзи, никнеймы, обращения, ссылки и Markdown. "
                    "Не пиши о судьбе, легендах, великих свершениях и новых главах истории. "
                    "Фраза должна содержать от 6 до 18 слов. Верни только саму фразу."
                ),
            ),
            AiMessage(
                "user",
                (
                    f"Тема: {theme_for(member_id)}. "
                    f"Время суток: {current_time:%H:%M}. "
                    f"Маркер варианта: {marker}."
                ),
            ),
        )

        try:
            async with self._semaphore:
                raw_line = await asyncio.wait_for(
                    self._ai_client.complete(messages, temperature=0.9, max_tokens=80),
                    timeout=self._timeout_seconds,
                )
        except (AiClientError, asyncio.TimeoutError, OSError) as error:
            logger.warning("Не удалось сгенерировать приветственную реплику: %s", error)
            return fallback

        return sanitize_generated_line(raw_line) or fallback


def _variant_marker(member_id: int, current_time: dt.datetime) -> str:
    source = f"{member_id}:{current_time.isoformat()}:{secrets.token_hex(4)}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:10]
