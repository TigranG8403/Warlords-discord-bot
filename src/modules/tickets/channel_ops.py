from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

import discord

from .catalog import TicketTypeSpec


@dataclass(slots=True, frozen=True)
class TicketCreationContext:
    guild: discord.Guild
    creator: discord.Member
    category: discord.CategoryChannel
    staff_role: discord.Role


def derive_ticket_subject(ticket_type: TicketTypeSpec, submission: dict[str, str]) -> str:
    subject = submission.get("subject") or submission.get("fraction_name") or submission.get("city_name")
    if subject and subject.strip():
        return subject.strip()

    first_value = next((value.strip() for value in submission.values() if value.strip()), ticket_type.label)
    return first_value


def build_ticket_channel_name(prefix: str, display_name: str, user_id: int) -> str:
    normalized_name = unicodedata.normalize("NFKD", display_name)
    ascii_name = normalized_name.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")
    if not slug:
        slug = "user"
    slug = slug[:20]
    return f"{prefix}-{slug}-{str(user_id)[-4:]}"


def build_ticket_overwrites(
    guild: discord.Guild,
    creator: discord.Member,
    staff_role: discord.Role,
) -> dict[discord.abc.Snowflake, discord.PermissionOverwrite]:
    return {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        creator: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            add_reactions=True,
            external_emojis=True,
        ),
        staff_role: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            add_reactions=True,
            external_emojis=True,
            manage_messages=True,
            manage_channels=True,
        ),
    }


async def create_ticket_channel(
    *,
    context: TicketCreationContext,
    ticket_type: TicketTypeSpec,
    channel_name: str,
) -> discord.TextChannel:
    return await context.guild.create_text_channel(
        name=channel_name,
        category=context.category,
        overwrites=build_ticket_overwrites(context.guild, context.creator, context.staff_role),
        topic=f"ticket_type={ticket_type.key};creator_id={context.creator.id}",
        reason=f"Создание тикета {ticket_type.key} пользователем {context.creator.id}",
    )


async def delete_ticket_channel(
    channel: discord.TextChannel,
    *,
    reason: str,
    logger: logging.Logger,
) -> None:
    try:
        await channel.delete(reason=reason)
    except discord.NotFound:
        return
    except (discord.Forbidden, discord.HTTPException) as error:
        logger.warning("Не удалось удалить канал %s: %s", channel.id, error)
