from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import discord

from core.discord_interactions import safe_followup_send, safe_send_ephemeral

from .catalog import STATUS_IN_PROGRESS, STATUS_WAITING_USER, get_ticket_type
from .channel_ops import delete_ticket_channel
from .config import TicketGuildSettings, get_msk_time, get_utc_time
from .repository import TicketRecord


logger = logging.getLogger(__name__)


class TicketServiceTicketOpsMixin:
    async def call_staff(self, interaction: discord.Interaction) -> None:
        context = await self._resolve_channel_context(interaction)
        if context is None:
            return

        channel, member, record = context
        guild_settings = self.get_guild_settings(channel.guild.id)
        if guild_settings is None:
            await self._send_context_error(
                interaction,
                "❌ Система тикетов не настроена. Администратор должен выполнить `/tickets settings set`.",
            )
            return

        staff_role = channel.guild.get_role(guild_settings.support_role_id)
        if staff_role is None:
            await self._send_context_error(interaction, "❌ Staff-роль больше не найдена.")
            return

        staff_call_cooldown = timedelta(minutes=guild_settings.staff_call_cooldown_minutes)
        if record.last_staff_call_at is not None:
            elapsed = get_utc_time() - record.last_staff_call_at
            if elapsed < staff_call_cooldown:
                retry_after = staff_call_cooldown - elapsed
                minutes, seconds = divmod(int(retry_after.total_seconds()), 60)
                await self._send_context_error(
                    interaction,
                    f"🔔 Staff уже вызывали. Попробуйте снова через {minutes} мин {seconds} сек.",
                )
                return

        if not await self._safe_defer_response(interaction, ephemeral=True):
            return

        embed = discord.Embed(
            description=f"🔔 {member.mention} вызвал(а) staff в тикет.",
            color=self.settings.embed_color,
            timestamp=get_msk_time(),
        )
        embed.set_footer(text=f"Тикет #{record.id}")

        ping_message = await channel.send(staff_role.mention)
        staff_message = await channel.send(embed=embed)

        self.repository.set_last_staff_call_at(channel.id, get_utc_time())
        await safe_followup_send(interaction, "✅ Staff оповещён.", ephemeral=True)

        await asyncio.sleep(20)
        for message in (ping_message, staff_message):
            try:
                await message.delete()
            except (discord.NotFound, discord.Forbidden):
                continue
            except discord.HTTPException as error:
                if getattr(error, "code", None) == 10003:
                    continue
                logger.warning(
                    "Не удалось удалить служебное сообщение в канале %s: %s",
                    channel.id,
                    error,
                )

    async def claim_ticket(self, interaction: discord.Interaction) -> None:
        context = await self._resolve_channel_context(interaction)
        if context is None:
            return

        channel, member, record = context
        guild_settings = self.get_guild_settings(channel.guild.id)
        if not self._is_staff(member, guild_settings):
            await self._send_context_error(interaction, "❌ Только staff может взять тикет в работу.")
            return

        if not await self._safe_defer_response(interaction, ephemeral=True):
            return

        updated_record = self.repository.assign_ticket(channel.id, member.id, STATUS_IN_PROGRESS, get_utc_time())
        if updated_record is None:
            await safe_followup_send(interaction, "❌ Не удалось обновить тикет в базе.", ephemeral=True)
            return

        await self.refresh_ticket_message(channel, updated_record)
        await channel.send(f"🛠️ Тикет взят в работу пользователем {member.mention}.")
        await safe_followup_send(interaction, "✅ Тикет назначен на вас.", ephemeral=True)

    async def mark_waiting_user(self, interaction: discord.Interaction) -> None:
        context = await self._resolve_channel_context(interaction)
        if context is None:
            return

        channel, member, record = context
        guild_settings = self.get_guild_settings(channel.guild.id)
        if not self._is_staff(member, guild_settings):
            await self._send_context_error(interaction, "❌ Только staff может перевести тикет в ожидание.")
            return

        if not await self._safe_defer_response(interaction, ephemeral=True):
            return

        updated_record = self.repository.assign_ticket(
            channel.id,
            record.assigned_to or member.id,
            STATUS_WAITING_USER,
            get_utc_time(),
        )
        if updated_record is None:
            await safe_followup_send(interaction, "❌ Не удалось обновить тикет в базе.", ephemeral=True)
            return

        await self.refresh_ticket_message(channel, updated_record)
        await channel.send(f"⌛ {member.mention} перевёл(а) тикет в режим ожидания игрока.")
        await safe_followup_send(interaction, "✅ Статус обновлён.", ephemeral=True)

    async def close_ticket(self, interaction: discord.Interaction, reason: str) -> None:
        if not await self._safe_defer_response(interaction, ephemeral=True, thinking=True):
            return

        context = await self._resolve_channel_context(interaction)
        if context is None:
            return

        channel, member, record = context
        guild_settings = self.get_guild_settings(channel.guild.id)
        if not self._can_close_ticket(member, record, guild_settings):
            await safe_followup_send(interaction, "❌ У вас нет прав для закрытия этого тикета.", ephemeral=True)
            return

        ticket_type = get_ticket_type(record.ticket_type)
        transcript_content = await self.renderers.create_transcript(channel, record, close_reason=reason)
        transcript_file = self.renderers.make_transcript_file(transcript_content, channel.name)

        closed_at = get_utc_time()
        self.repository.mark_closed(
            channel.id,
            closed_by=member.id,
            close_reason=reason,
            closed_at=closed_at,
        )

        await self.notifications.send_logs(
            guild=channel.guild,
            log_channel_id=guild_settings.log_channel_id if guild_settings is not None else None,
            record=record,
            closed_by=member,
            ticket_type=ticket_type,
            transcript_file=transcript_file,
            reason=reason,
            closed_at=closed_at,
            logger=logger,
        )
        await self.notifications.send_creator_dm(
            client=interaction.client,
            record=record,
            closed_by=member,
            ticket_type=ticket_type,
            transcript_content=transcript_content,
            reason=reason,
            closed_at=closed_at,
            logger=logger,
        )

        await safe_followup_send(
            interaction,
            "✅ Тикет закрыт, транскрипт сохранён. Канал будет удалён.",
            ephemeral=True,
        )
        await delete_ticket_channel(
            channel,
            reason=f"Закрытие тикета: {reason}",
            logger=logger,
        )

    async def refresh_ticket_message(self, channel: discord.TextChannel, record: TicketRecord) -> None:
        if record.message_id == 0:
            return

        try:
            message = await channel.fetch_message(record.message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            logger.warning("Не удалось обновить главное сообщение тикета в канале %s.", channel.id)
            return

        from .views.inside import TicketControlView

        await message.edit(
            embed=self.renderers.build_ticket_embed(record, channel.guild),
            view=TicketControlView(self),
        )

    async def create_transcript(
        self,
        channel: discord.TextChannel,
        record: TicketRecord,
        *,
        close_reason: str,
    ) -> str:
        return await self.renderers.create_transcript(channel, record, close_reason=close_reason)

    def build_ticket_embed(self, record: TicketRecord, guild: discord.Guild) -> discord.Embed:
        return self.renderers.build_ticket_embed(record, guild)

    def make_transcript_file(self, transcript_content: str, channel_name: str) -> discord.File:
        return self.renderers.make_transcript_file(transcript_content, channel_name)

    async def _resolve_channel_context(
        self,
        interaction: discord.Interaction,
    ) -> tuple[discord.TextChannel, discord.Member, TicketRecord] | None:
        channel = interaction.channel
        if channel is None or not isinstance(channel, discord.TextChannel):
            await self._send_context_error(interaction, "❌ Канал тикета недоступен.")
            return None

        if not isinstance(interaction.user, discord.Member):
            await self._send_context_error(interaction, "❌ Не удалось определить участника сервера.")
            return None

        record = self.repository.get_by_channel_id(channel.id)
        if record is None:
            await self._send_context_error(interaction, "⚠️ Для этого канала не найден тикет в базе.")
            return None

        return channel, interaction.user, record

    async def _send_context_error(self, interaction: discord.Interaction, message: str) -> None:
        await safe_send_ephemeral(interaction, message)
