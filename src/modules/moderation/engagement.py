from __future__ import annotations

import re
import time

import discord

from .memory import PersonaMemoryEntry, PersonaMemoryStore

_MENTION_TOKEN_RE = re.compile(r"<@!?\d+>|<@&\d+>")
_ACK_WORDS = {
    "ок",
    "окей",
    "ага",
    "угу",
    "пон",
    "понял",
    "понятно",
    "ясно",
    "лан",
    "ладно",
    "хех",
    "хм",
    "мм",
}


def is_protected_member(member: discord.Member, guild: discord.Guild, bot_user_id: int | None) -> bool:
    if member.id == guild.owner_id:
        return True
    if bot_user_id is not None and member.id == bot_user_id:
        return True
    permissions = member.guild_permissions
    if permissions.administrator or permissions.manage_guild or permissions.manage_messages or permissions.moderate_members:
        return True
    bot_member = guild.me
    if bot_member is None:
        return False
    return member.top_role >= bot_member.top_role


def is_reply_to_bot(message: discord.Message, bot_user_id: int | None) -> bool:
    if bot_user_id is None or message.reference is None:
        return False
    resolved = message.reference.resolved
    if isinstance(resolved, discord.Message):
        return resolved.author.id == bot_user_id
    cached = getattr(message.reference, "cached_message", None)
    if isinstance(cached, discord.Message):
        return cached.author.id == bot_user_id
    return False


def is_bot_mentioned(message: discord.Message, bot_user_id: int | None) -> bool:
    if bot_user_id is None:
        return False
    return any(user.id == bot_user_id for user in message.mentions)


def is_bot_role_mentioned(
    message: discord.Message,
    *,
    bot_user: discord.ClientUser | None,
    bot_member: discord.Member | None,
) -> bool:
    role_mentions = tuple(getattr(message, "role_mentions", ()))
    if not role_mentions:
        return False

    bot_role_ids = {role.id for role in getattr(bot_member, "roles", ()) if getattr(role, "id", None) is not None}
    if any(getattr(role, "id", None) in bot_role_ids for role in role_mentions):
        return True

    candidates: set[str] = set()
    for raw in (
        getattr(bot_user, "name", ""),
        getattr(bot_user, "global_name", ""),
        getattr(bot_member, "display_name", ""),
        getattr(bot_member, "nick", ""),
    ):
        normalized = str(raw).strip().lower()
        if not normalized:
            continue
        candidates.add(normalized)
        candidates.add(normalized.replace("[", "").replace("]", "").strip())

    candidates = {item for item in candidates if item}
    if not candidates:
        return False

    for role in role_mentions:
        normalized_role_name = str(getattr(role, "name", "")).strip().lower()
        if not normalized_role_name:
            continue
        normalized_candidates = {
            normalized_role_name,
            normalized_role_name.replace("[", "").replace("]", "").strip(),
        }
        if candidates & normalized_candidates:
            return True
    return False


def is_textually_addressed_to_bot(
    message: discord.Message,
    *,
    bot_user: discord.ClientUser | None,
    bot_member: discord.Member | None,
) -> bool:
    content = " ".join((message.content or "").split()).strip().lower()
    if not content:
        return False

    candidates: set[str] = set()
    for raw in (
        getattr(bot_user, "name", ""),
        getattr(bot_user, "global_name", ""),
        getattr(bot_member, "display_name", ""),
        getattr(bot_member, "nick", ""),
    ):
        normalized = str(raw).strip().lower()
        if not normalized:
            continue
        candidates.add(normalized)
        candidates.add(normalized.replace("[", "").replace("]", "").strip())

    candidates = {item for item in candidates if item}
    if not candidates:
        return False

    for candidate in sorted(candidates, key=len, reverse=True):
        pattern = rf"(^|[\s,.:;!?])@?{re.escape(candidate)}(?=$|[\s,.:;!?])"
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False


def should_continue_persona_dialogue(
    *,
    message: discord.Message,
    memory_entry: PersonaMemoryEntry | None,
    continue_window_seconds: int = 90,
) -> bool:
    if memory_entry is None or memory_entry.topic != "dialogue":
        return False
    if int(time.time()) - memory_entry.remembered_at > continue_window_seconds:
        return False

    content = " ".join((message.content or "").split()).strip()
    if not content:
        return False
    if content.startswith("/"):
        return False
    if getattr(message, "mentions", None) or getattr(message, "role_mentions", None):
        return False
    if re.search(r"https?://|discord\.gg/|t\.me/|vk\.com/", content, re.IGNORECASE):
        return False
    return True


def should_suppress_persona_text_reply(message: discord.Message, reply_text: str) -> bool:
    if not reply_text:
        return False
    content = (message.content or "").strip()
    if content:
        return False
    if not message.attachments:
        return False
    return True


def is_low_signal_persona_message(content: str) -> bool:
    normalized = _normalize_persona_signal_text(content)
    if not normalized:
        return False
    lowered = normalized.casefold()
    if lowered in _ACK_WORDS:
        return True
    if re.search(r"[a-zа-яё0-9]", lowered, re.IGNORECASE):
        return False
    return len(normalized) <= 8


def should_skip_duplicate_persona_reply(
    *,
    current_user_content: str,
    previous_user_content: str,
    previous_bot_reply: str,
    recent_bot_replies: tuple[str, ...] = (),
    candidate_reply: str,
    reaction_emoji: str,
    previous_remembered_at: int = 0,
    duplicate_window_seconds: int = 30,
    repeat_window_seconds: int = 180,
) -> bool:
    if reaction_emoji:
        return False
    if previous_remembered_at <= 0:
        return False
    age_seconds = int(time.time()) - previous_remembered_at
    current = " ".join(current_user_content.split()).strip().lower()
    previous_user = " ".join(previous_user_content.split()).strip().lower()
    previous_bot = " ".join(previous_bot_reply.split()).strip()
    candidate = " ".join(candidate_reply.split()).strip()
    if not current or not previous_user or not previous_bot or not candidate:
        return False
    if age_seconds <= duplicate_window_seconds and current == previous_user and candidate == previous_bot:
        return True
    if age_seconds > repeat_window_seconds:
        return False
    recent = tuple(" ".join(item.split()).strip() for item in recent_bot_replies if item.strip())
    if not recent:
        return False
    if current == previous_user:
        return False
    return candidate in recent


def should_skip_recent_channel_duplicate_reply(
    *,
    candidate_reply: str,
    recent_channel_replies: tuple[str, ...],
    current_user_content: str,
) -> bool:
    if not is_low_signal_persona_message(current_user_content):
        return False
    candidate = " ".join(candidate_reply.split()).strip()
    if not candidate:
        return False
    recent = {" ".join(item.split()).strip() for item in recent_channel_replies if item.strip()}
    return candidate in recent


def remember_persona_context(
    memory_store: PersonaMemoryStore,
    *,
    message: discord.Message,
    bot_reply: str,
) -> None:
    if message.guild is None:
        return
    memory_store.remember(
        guild_id=message.guild.id,
        channel_id=message.channel.id,
        user_id=message.author.id,
        topic="dialogue",
        last_user_content=message.content,
        last_bot_reply=bot_reply,
    )
    memory_store.remember_channel_reply(
        guild_id=message.guild.id,
        channel_id=message.channel.id,
        reply_text=bot_reply,
    )


def remember_channel_reply(
    memory_store: PersonaMemoryStore,
    *,
    message: discord.Message,
    bot_reply: str,
) -> None:
    if message.guild is None:
        return
    memory_store.remember_channel_reply(
        guild_id=message.guild.id,
        channel_id=message.channel.id,
        reply_text=bot_reply,
    )


def _normalize_persona_signal_text(text: str) -> str:
    stripped = _MENTION_TOKEN_RE.sub(" ", text or "")
    return " ".join(stripped.split()).strip()
