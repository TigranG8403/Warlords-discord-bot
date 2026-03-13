from __future__ import annotations

from io import BytesIO

import discord

from .catalog import get_status_label, get_ticket_type
from .config import TicketsSettings, convert_to_msk, get_msk_time
from .repository import TicketRecord


def truncate_for_field(value: str, limit: int = 1024) -> str:
    if len(value) <= limit:
        return value
    return value[: max(limit - 3, 0)] + "..."


class TicketRenderers:
    def __init__(self, settings: TicketsSettings) -> None:
        self.settings = settings

    def build_ticket_embed(self, record: TicketRecord, guild: discord.Guild) -> discord.Embed:
        ticket_type = get_ticket_type(record.ticket_type)
        embed = discord.Embed(
            title=f"{ticket_type.emoji} {ticket_type.label}",
            description=ticket_type.intro,
            color=ticket_type.color(self.settings),
            timestamp=convert_to_msk(record.created_at),
        )
        embed.add_field(name="Автор", value=f"<@{record.creator_id}>", inline=True)
        embed.add_field(name="Статус", value=get_status_label(record.status), inline=True)
        embed.add_field(
            name="Ответственный",
            value=f"<@{record.assigned_to}>" if record.assigned_to else "Не назначен",
            inline=True,
        )

        for field in ticket_type.fields:
            value = record.details.get(field.key, "—").strip() or "—"
            embed.add_field(name=field.label, value=truncate_for_field(value), inline=False)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"Тикет #{record.id} • Создан")
        return embed

    async def create_transcript(
        self,
        channel: discord.TextChannel,
        record: TicketRecord,
        *,
        close_reason: str,
    ) -> str:
        ticket_type = get_ticket_type(record.ticket_type)
        messages: list[str] = []
        async for message in channel.history(limit=None, oldest_first=True):
            msk_time = convert_to_msk(message.created_at)
            time_str = msk_time.strftime("%Y-%m-%d %H:%M:%S МСК")
            message_content = self.format_message_content(message)
            author_name = message.author.display_name
            messages.append(f"[{time_str}] {author_name}: {message_content}")

        created_at = convert_to_msk(record.created_at)
        transcript_content = "\ufeff"
        transcript_content += f"Транскрипт тикета #{record.id}\n"
        transcript_content += f"Тип: {ticket_type.label}\n"
        transcript_content += f"Тема: {record.subject}\n"
        transcript_content += f"Создатель: {record.creator_id}\n"
        transcript_content += f"Ответственный: {record.assigned_to or 'не назначен'}\n"
        transcript_content += f"Канал: {channel.name} ({channel.id})\n"
        transcript_content += f"Дата создания: {created_at.strftime('%Y-%m-%d %H:%M:%S МСК')}\n"
        transcript_content += f"Причина закрытия: {close_reason}\n"
        transcript_content += "=" * 60 + "\n"
        transcript_content += "Анкета:\n"
        for field in ticket_type.fields:
            transcript_content += f"- {field.label}: {record.details.get(field.key, '—')}\n"
        transcript_content += "=" * 60 + "\n\n"
        transcript_content += "\n".join(messages)
        return transcript_content

    def make_transcript_file(self, transcript_content: str, channel_name: str) -> discord.File:
        transcript_bytes = BytesIO(transcript_content.encode("utf-8"))
        current_time = get_msk_time()
        return discord.File(
            transcript_bytes,
            filename=f"transcript_{channel_name}_{current_time.strftime('%Y%m%d_%H%M%S')}.txt",
        )

    def format_message_content(self, message: discord.Message) -> str:
        content = message.clean_content.strip()
        if not content and message.embeds:
            content = "[Встроенный контент]"
        if not content:
            content = "[Сообщение без текста]"

        if message.attachments:
            attachment_links = ", ".join(attachment.url for attachment in message.attachments)
            content = f"{content} [Вложения: {attachment_links}]"

        return content
