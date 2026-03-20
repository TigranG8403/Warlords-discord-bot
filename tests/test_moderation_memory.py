from __future__ import annotations

import time
import unittest

from tests import support  # noqa: F401
from modules.moderation.memory import PersonaMemoryStore


class ModerationMemoryTests(unittest.TestCase):
    def test_store_returns_recent_entry(self) -> None:
        store = PersonaMemoryStore(ttl_seconds=60)
        store.remember(
            guild_id=1,
            channel_id=2,
            user_id=3,
            topic="opening",
            last_user_content="когда открытие?",
            last_bot_reply="Завтра в три.",
        )

        entry = store.get(guild_id=1, channel_id=2, user_id=3)

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.topic, "opening")
        self.assertEqual(entry.last_bot_reply, "Завтра в три.")

    def test_store_expires_entries(self) -> None:
        store = PersonaMemoryStore(ttl_seconds=30)
        store.remember(
            guild_id=1,
            channel_id=2,
            user_id=3,
            topic="opening",
            last_user_content="когда открытие?",
            last_bot_reply="Завтра в три.",
        )
        key = (1, 2, 3)
        store._entries[key].expires_at = int(time.time()) - 1  # noqa: SLF001

        entry = store.get(guild_id=1, channel_id=2, user_id=3)

        self.assertIsNone(entry)

    def test_store_remembers_recent_channel_replies(self) -> None:
        store = PersonaMemoryStore(ttl_seconds=60)
        store.remember_channel_reply(guild_id=1, channel_id=2, reply_text="Первый ответ.")
        store.remember_channel_reply(guild_id=1, channel_id=2, reply_text="Второй ответ.")

        replies = store.recent_channel_replies(guild_id=1, channel_id=2)

        self.assertEqual(replies, ("Первый ответ.", "Второй ответ."))


if __name__ == "__main__":
    unittest.main()
