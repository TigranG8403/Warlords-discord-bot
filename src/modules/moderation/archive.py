from __future__ import annotations

import discord

from .config import ModerationDecision, ModerationEvaluationInput
from .repository import ModerationRepository


def build_archive_embed(
    *,
    message: discord.Message,
    payload: ModerationEvaluationInput,
    decision: ModerationDecision,
) -> discord.Embed:
    title_map = {
        "warning": "Предупреждение",
        "light_violation": "Автомут",
        "ban_violation": "Автобан",
        "scam_alert": "Пинг модерации",
        "review": "Нужна ручная проверка",
    }
    color_map = {
        "warning": 0xC9A238,
        "light_violation": 0xC96B38,
        "ban_violation": 0xB93D3D,
        "scam_alert": 0xD48B3C,
        "review": 0x5B6D8A,
    }
    embed = discord.Embed(
        title=f"{title_map.get(decision.decision, 'Событие модерации')} • {payload.author_display_name}",
        description=(payload.content or "*Пустое сообщение*")[:4000],
        color=color_map.get(decision.decision, 0x6A4C93),
    )
    embed.add_field(name="Нарушитель", value=f"<@{payload.author_id}>", inline=True)
    embed.add_field(name="Канал", value=message.channel.mention, inline=True)
    embed.add_field(name="Решение", value=decision.decision, inline=True)
    embed.add_field(name="Причина", value=decision.reason[:1024] or "Не указана", inline=False)
    embed.add_field(name="Метки", value=", ".join(decision.labels) if decision.labels else "нет", inline=True)
    embed.add_field(name="Источник", value=f"{decision.source} ({decision.confidence:.2f})", inline=True)
    if decision.timeout_minutes > 0:
        embed.add_field(name="Timeout", value=f"{decision.timeout_minutes} мин.", inline=True)
    if payload.attachment_urls:
        embed.add_field(name="Вложения", value="\n".join(payload.attachment_urls)[:1024], inline=False)
    if payload.attachment_ocr_texts:
        preview = "\n".join(f"• {item[:220]}" for item in payload.attachment_ocr_texts if item.strip())
        if preview:
            embed.add_field(name="OCR", value=preview[:1024], inline=False)
    if payload.recent_messages:
        context_preview = "\n".join(f"• {item.author_name}: {item.content[:140]}" for item in payload.recent_messages[-4:])
        embed.add_field(name="Контекст", value=context_preview[:1024], inline=False)
    return embed


def build_compact_archive_search_text(payload: ModerationEvaluationInput) -> str:
    return f"-# search: <@{payload.author_id}> {payload.author_display_name} @{payload.author_name} {payload.author_id}"


def build_archive_search_text(payload: ModerationEvaluationInput) -> str:
    return (
        f"Нарушитель: <@{payload.author_id}> | "
        f"Ник: {payload.author_display_name} | "
        f"Тег: @{payload.author_name}"
    )


def enrich_reply_mentions(guild: discord.Guild | None, reply_text: str, repository: ModerationRepository) -> str:
    if guild is None or not reply_text.strip():
        return reply_text

    result = reply_text
    channels = sorted(
        (
            channel
            for channel in getattr(guild, "channels", ())
            if hasattr(channel, "id") and hasattr(channel, "name")
        ),
        key=lambda channel: len(channel.name),
        reverse=True,
    )
    for channel in channels:
        result = result.replace(f"#{channel.name}", f"<#{channel.id}>")

    member_aliases: list[tuple[str, int]] = []
    for member in getattr(guild, "members", ()):
        if getattr(member, "bot", False):
            continue
        member_aliases.append((getattr(member, "display_name", "").strip(), member.id))
        member_aliases.append((getattr(member, "name", "").strip(), member.id))

    for alias, user_id in sorted({(alias, user_id) for alias, user_id in member_aliases if alias}, key=lambda item: len(item[0]), reverse=True):
        result = result.replace(f"@{alias}", f"<@{user_id}>")

    for profile in repository.list_known_profiles(limit=40):
        for alias in sorted({profile.primary_name, *profile.aliases}, key=len, reverse=True):
            if alias:
                result = result.replace(f"@{alias}", f"<@{profile.discord_id}>")

    return result
