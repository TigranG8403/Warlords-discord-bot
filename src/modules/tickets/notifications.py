from __future__ import annotations

from io import BytesIO

import discord

from .catalog import TicketTypeSpec
from .config import TicketsSettings, convert_to_msk
from .renderers import truncate_for_field
from .repository import TicketRecord


class TicketNotifications:
    def __init__(self, settings: TicketsSettings) -> None:
        self.settings = settings

    async def send_logs(
        self,
        *,
        guild: discord.Guild,
        log_channel_id: int | None,
        record: TicketRecord,
        closed_by: discord.Member,
        ticket_type: TicketTypeSpec,
        transcript_file: discord.File,
        reason: str,
        closed_at,
        logger,
    ) -> None:
        if log_channel_id is None:
            logger.warning("Не удалось отправить лог по тикету %s: лог-канал не настроен.", record.id)
            return

        logs_channel = guild.get_channel(log_channel_id)
        if not isinstance(logs_channel, discord.TextChannel):
            logger.warning("Лог-канал %s не найден.", log_channel_id)
            return

        embed = discord.Embed(
            title="Тикет закрыт",
            color=self.settings.embed_color,
            timestamp=convert_to_msk(closed_at),
        )
        embed.add_field(name="Тикет", value=f"#{record.id} • {ticket_type.label}", inline=False)
        embed.add_field(name="Автор", value=f"<@{record.creator_id}>", inline=True)
        embed.add_field(name="Закрыл", value=closed_by.mention, inline=True)
        embed.add_field(name="Причина", value=truncate_for_field(reason), inline=False)
        embed.add_field(
            name="Ответственный",
            value=f"<@{record.assigned_to}>" if record.assigned_to else "Не назначен",
            inline=False,
        )

        await logs_channel.send(embed=embed, file=transcript_file)

    async def send_creator_dm(
        self,
        *,
        client: discord.Client,
        record: TicketRecord,
        closed_by: discord.Member,
        ticket_type: TicketTypeSpec,
        transcript_content: str,
        reason: str,
        closed_at,
        logger,
    ) -> None:
        user = client.get_user(record.creator_id)
        if user is None:
            try:
                user = await client.fetch_user(record.creator_id)
            except discord.HTTPException:
                logger.warning(
                    "Не удалось получить пользователя %s для отправки транскрипта.",
                    record.creator_id,
                )
                return

        dm_embed = discord.Embed(
            title="Тикет закрыт",
            description=f"Ваш тикет **{ticket_type.label}** был закрыт.",
            color=self.settings.embed_color,
            timestamp=convert_to_msk(closed_at),
        )
        dm_embed.add_field(name="Тема", value=truncate_for_field(record.subject), inline=False)
        dm_embed.add_field(name="Закрыл", value=closed_by.display_name, inline=True)
        dm_embed.add_field(name="Причина", value=truncate_for_field(reason), inline=False)

        try:
            await user.send(
                embed=dm_embed,
                file=discord.File(
                    BytesIO(transcript_content.encode("utf-8")),
                    filename=f"transcript_ticket_{record.id}.txt",
                ),
            )
        except discord.Forbidden:
            logger.info(
                "Не удалось отправить DM пользователю %s: личные сообщения закрыты.",
                record.creator_id,
            )
        except discord.HTTPException as error:
            logger.warning("Не удалось отправить DM пользователю %s: %s", record.creator_id, error)
