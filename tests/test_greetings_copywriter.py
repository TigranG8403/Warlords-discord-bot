from __future__ import annotations

import asyncio
from datetime import datetime
import unittest

from tests import support  # noqa: F401

from modules.greetings.content import fallback_line
from modules.greetings.copywriter import GreetingCopywriter


class _FakeAiClient:
    def __init__(self, response: str) -> None:
        self.response = response

    async def complete(self, _messages, **_kwargs) -> str:
        return self.response


class _SlowAiClient:
    async def complete(self, _messages, **_kwargs) -> str:
        await asyncio.sleep(0.1)
        return "Ответ пришёл слишком поздно для приветственного сообщения."


class GreetingCopywriterTests(unittest.TestCase):
    def test_valid_ai_response_is_used(self) -> None:
        copywriter = GreetingCopywriter(
            _FakeAiClient("На площади сегодня нашлось место ещё для одного голоса."),
        )

        result = asyncio.run(
            copywriter.create_line(member_id=1, current_time=datetime(2026, 7, 30, 12, 0))
        )

        self.assertEqual(result, "На площади сегодня нашлось место ещё для одного голоса.")

    def test_invalid_ai_response_uses_fallback(self) -> None:
        copywriter = GreetingCopywriter(_FakeAiClient("Легенда начинается!"))

        result = asyncio.run(
            copywriter.create_line(member_id=2, current_time=datetime(2026, 7, 30, 12, 0))
        )

        self.assertEqual(result, fallback_line(2))

    def test_timeout_uses_fallback(self) -> None:
        copywriter = GreetingCopywriter(_SlowAiClient(), timeout_seconds=0.01)

        with self.assertLogs("modules.greetings.copywriter", level="WARNING"):
            result = asyncio.run(
                copywriter.create_line(
                    member_id=3,
                    current_time=datetime(2026, 7, 30, 12, 0),
                )
            )

        self.assertEqual(result, fallback_line(3))
