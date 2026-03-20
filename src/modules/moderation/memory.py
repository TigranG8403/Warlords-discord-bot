from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(slots=True)
class PersonaMemoryEntry:
    topic: str
    last_user_content: str
    last_bot_reply: str
    remembered_at: int
    expires_at: int


@dataclass(slots=True)
class ChannelReplyEntry:
    replies: tuple[str, ...]
    expires_at: int


class PersonaMemoryStore:
    def __init__(self, *, ttl_seconds: int = 300, max_entries: int = 512) -> None:
        self.ttl_seconds = max(30, ttl_seconds)
        self.max_entries = max(32, max_entries)
        self._entries: dict[tuple[int, int, int], PersonaMemoryEntry] = {}
        self._channel_replies: dict[tuple[int, int], ChannelReplyEntry] = {}

    def get(self, *, guild_id: int, channel_id: int, user_id: int) -> PersonaMemoryEntry | None:
        self._prune()
        key = (guild_id, channel_id, user_id)
        entry = self._entries.get(key)
        if entry is None or entry.expires_at <= int(time.time()):
            self._entries.pop(key, None)
            return None
        return entry

    def remember(
        self,
        *,
        guild_id: int,
        channel_id: int,
        user_id: int,
        topic: str,
        last_user_content: str,
        last_bot_reply: str,
    ) -> None:
        self._prune()
        if len(self._entries) >= self.max_entries:
            oldest_key = min(self._entries.items(), key=lambda item: item[1].expires_at)[0]
            self._entries.pop(oldest_key, None)
        self._entries[(guild_id, channel_id, user_id)] = PersonaMemoryEntry(
            topic=topic,
            last_user_content=last_user_content,
            last_bot_reply=last_bot_reply,
            remembered_at=int(time.time()),
            expires_at=int(time.time()) + self.ttl_seconds,
        )

    def clear(self, *, guild_id: int, channel_id: int, user_id: int) -> None:
        self._entries.pop((guild_id, channel_id, user_id), None)

    def recent_channel_replies(self, *, guild_id: int, channel_id: int) -> tuple[str, ...]:
        self._prune()
        key = (guild_id, channel_id)
        entry = self._channel_replies.get(key)
        if entry is None or entry.expires_at <= int(time.time()):
            self._channel_replies.pop(key, None)
            return ()
        return entry.replies

    def remember_channel_reply(self, *, guild_id: int, channel_id: int, reply_text: str) -> None:
        normalized = " ".join(reply_text.split()).strip()
        if not normalized:
            return
        self._prune()
        key = (guild_id, channel_id)
        existing = self._channel_replies.get(key)
        replies = list(existing.replies if existing is not None else ())
        replies.append(normalized)
        replies = replies[-3:]
        self._channel_replies[key] = ChannelReplyEntry(
            replies=tuple(replies),
            expires_at=int(time.time()) + self.ttl_seconds,
        )

    def _prune(self) -> None:
        now = int(time.time())
        expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)
        expired_channels = [key for key, entry in self._channel_replies.items() if entry.expires_at <= now]
        for key in expired_channels:
            self._channel_replies.pop(key, None)
