from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from tests import support  # noqa: F401
from modules.moderation.module import _detect_reply_to_bot


class ModerationModuleTests(unittest.IsolatedAsyncioTestCase):
    async def test_detect_reply_to_bot_uses_cached_reference_when_available(self) -> None:
        referenced_message = SimpleNamespace(author=SimpleNamespace(id=77))
        message = SimpleNamespace(
            reference=SimpleNamespace(
                resolved=referenced_message,
                cached_message=None,
                message_id=123,
                channel_id=555,
            ),
        )

        result = await _detect_reply_to_bot(message, 77)

        self.assertTrue(result)

    async def test_detect_reply_to_bot_fetches_reference_when_not_cached(self) -> None:
        fetched_message = SimpleNamespace(author=SimpleNamespace(id=77))
        channel = SimpleNamespace(fetch_message=AsyncMock(return_value=fetched_message))
        guild = SimpleNamespace(
            get_channel_or_thread=lambda channel_id: channel if channel_id == 555 else None,
            fetch_channel=AsyncMock(return_value=None),
        )
        message = SimpleNamespace(
            reference=SimpleNamespace(
                resolved=None,
                cached_message=None,
                message_id=123,
                channel_id=555,
            ),
            guild=guild,
            channel=channel,
        )

        result = await _detect_reply_to_bot(message, 77)

        self.assertTrue(result)
        channel.fetch_message.assert_awaited_once_with(123)

    async def test_detect_reply_to_bot_returns_false_when_reference_is_not_bot(self) -> None:
        fetched_message = SimpleNamespace(author=SimpleNamespace(id=10))
        channel = SimpleNamespace(fetch_message=AsyncMock(return_value=fetched_message))
        guild = SimpleNamespace(
            get_channel_or_thread=lambda channel_id: channel if channel_id == 555 else None,
            fetch_channel=AsyncMock(return_value=None),
        )
        message = SimpleNamespace(
            reference=SimpleNamespace(
                resolved=None,
                cached_message=None,
                message_id=123,
                channel_id=555,
            ),
            guild=guild,
            channel=channel,
        )

        result = await _detect_reply_to_bot(message, 77)

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
