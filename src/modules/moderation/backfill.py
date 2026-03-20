from __future__ import annotations

import asyncio
import logging

import discord

from .ai_client import ModerationAiClient
from .engagement import is_bot_mentioned, is_reply_to_bot
from .repository import ModerationRepository


logger = logging.getLogger(__name__)


async def backfill_user_observations(
    *,
    repository: ModerationRepository,
    ai_client: ModerationAiClient | None,
    guild: discord.Guild,
    archive_channel_id: int | None,
    bot_user_id: int | None,
    reset_existing: bool,
    refresh_summaries: bool,
) -> dict[str, int]:
    if reset_existing:
        repository.clear_user_observations(guild_id=guild.id)

    scanned_channels = 0
    scanned_messages = 0
    bot_member = guild.me

    for channel in sorted(guild.text_channels, key=lambda item: item.position):
        if archive_channel_id is not None and channel.id == archive_channel_id:
            continue
        if bot_member is not None:
            permissions = channel.permissions_for(bot_member)
            if not permissions.view_channel or not permissions.read_message_history:
                continue

        scanned_channels += 1
        try:
            async for item in channel.history(limit=None, oldest_first=True):
                if item.author.bot or item.webhook_id is not None:
                    continue
                content = item.content.strip()
                if not content:
                    continue
                repository.record_user_observation(
                    guild_id=guild.id,
                    user_id=item.author.id,
                    author_name=getattr(item.author, "display_name", item.author.name),
                    role_names=_extract_role_names(item.author),
                    content=content,
                    decision="allow",
                    addressed_to_bot=is_reply_to_bot(item, bot_user_id) or is_bot_mentioned(item, bot_user_id),
                    labels=(),
                )
                scanned_messages += 1
        except discord.HTTPException as error:
            logger.warning("Не удалось дочитать историю канала %s во время backfill: %s", channel.id, error)

    summaries_updated = 0
    if ai_client is not None and ai_client.supports_persona() and refresh_summaries:
        for snapshot in repository.list_user_observation_snapshots(guild_id=guild.id, minimum_messages=2):
            summary = await asyncio.to_thread(
                ai_client.generate_user_character_summary,
                display_name=snapshot.display_name,
                role_names=snapshot.role_names,
                known_profile=format_known_profile_summary(repository, snapshot.user_id),
                recent_samples=snapshot.recent_samples,
                existing_summary=repository.describe_user_character(guild_id=guild.id, user_id=snapshot.user_id),
            )
            if summary:
                repository.save_user_character_summary(
                    guild_id=guild.id,
                    user_id=snapshot.user_id,
                    summary=summary,
                )
                summaries_updated += 1

    return {
        "channels": scanned_channels,
        "messages": scanned_messages,
        "users": len(repository.list_user_observation_snapshots(guild_id=guild.id, minimum_messages=1)),
        "summaries": summaries_updated,
    }


def format_known_profile_summary(repository: ModerationRepository, user_id: int) -> str:
    profile = repository.get_known_profile(user_id)
    if profile is None:
        return ""
    alias_text = f" ({', '.join(profile.aliases)})" if profile.aliases else ""
    return f"{profile.primary_name}{alias_text} — {profile.summary}"


def _extract_role_names(member: discord.abc.User) -> tuple[str, ...]:
    roles = getattr(member, "roles", ())
    collected: list[str] = []
    for role in roles:
        name = getattr(role, "name", "").strip()
        if not name or name == "@everyone":
            continue
        collected.append(name)
    return tuple(collected[-8:])
