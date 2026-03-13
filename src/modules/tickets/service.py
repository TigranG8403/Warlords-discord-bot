from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import discord

from core.discord_interactions import (
    is_acknowledged_interaction_error,
    safe_defer,
    safe_followup_send,
    safe_send_ephemeral,
)

from .catalog import (
    STATUS_IN_PROGRESS,
    STATUS_OPEN,
    STATUS_WAITING_USER,
    TicketTypeSpec,
    get_ticket_type,
)
from .channel_ops import (
    TicketCreationContext,
    build_ticket_channel_name,
    create_ticket_channel,
    delete_ticket_channel,
    derive_ticket_subject,
)
from .config import TicketGuildSettings, TicketsSettings, get_msk_time, get_utc_time
from .notifications import TicketNotifications
from .renderers import TicketRenderers
from .repository import TicketRecord, TicketRepository

logger = logging.getLogger(__name__)


class TicketService:
    def __init__(self, settings: TicketsSettings):
        self.settings = settings
        self.repository = TicketRepository(settings.database_path)
        self.repository.initialize()
        self.renderers = TicketRenderers(settings)
        self.notifications = TicketNotifications(settings)
        self._active_interaction_ids: set[int] = set()

    def get_guild_settings(self, guild_id: int) -> TicketGuildSettings | None:
        return self.repository.get_guild_settings(guild_id)

    def set_guild_settings(self, settings: TicketGuildSettings) -> None:
        self.repository.set_guild_settings(settings)

    def delete_guild_settings(self, guild_id: int) -> None:
        self.repository.delete_guild_settings(guild_id)

    def validate_guild_settings(
        self,
        guild: discord.Guild,
        settings: TicketGuildSettings,
        *,
        bot_member: discord.Member | None = None,
    ) -> list[str]:
        issues: list[str] = []

        role = guild.get_role(settings.support_role_id)
        if role is None:
            issues.append(f"staff role `{settings.support_role_id}` не найдена")

        if settings.staff_call_cooldown_minutes < 1:
            issues.append("staff cooldown должен быть не меньше 1 минуты")

        channel_checks = (
            ("основная категория тикетов", settings.ticket_category_id, discord.CategoryChannel),
            ("категория рекламы фракций", settings.fraction_category_id, discord.CategoryChannel),
            ("категория RP-тикетов", settings.rp_category_id, discord.CategoryChannel),
            ("лог-канал", settings.log_channel_id, discord.TextChannel),
        )

        for label, channel_id, expected_type in channel_checks:
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, expected_type):
                issues.append(f"{label} `{channel_id}` не найдена или имеет неверный тип")
                continue

            if bot_member is None:
                continue

            permissions = channel.permissions_for(bot_member)
            if isinstance(channel, discord.TextChannel):
                missing = [
                    permission
                    for permission, allowed in (
                        ("view_channel", permissions.view_channel),
                        ("send_messages", permissions.send_messages),
                        ("embed_links", permissions.embed_links),
                        ("attach_files", permissions.attach_files),
                    )
                    if not allowed
                ]
            else:
                missing = [
                    permission
                    for permission, allowed in (
                        ("view_channel", permissions.view_channel),
                        ("manage_channels", permissions.manage_channels),
                    )
                    if not allowed
                ]

            if missing:
                issues.append(f"у бота не хватает прав в '{channel.name}': {', '.join(missing)}")

        return issues

    async def create_ticket(
        self,
        interaction: discord.Interaction,
        ticket_type: TicketTypeSpec,
        submission: dict[str, str],
    ) -> None:
        if not await self._safe_defer_response(interaction, ephemeral=True, thinking=True):
            return

        context = await self._resolve_creation_context(interaction, ticket_type)
        if context is None:
            return

        existing_ticket = self.repository.get_active_by_creator_and_type(
            context.guild.id,
            context.creator.id,
            ticket_type.key,
        )
        if existing_ticket is not None:
            existing_channel = context.guild.get_channel(existing_ticket.channel_id)
            if isinstance(existing_channel, discord.TextChannel):
                await safe_followup_send(
                    interaction,
                    f"❌ У вас уже есть открытый тикет этого типа: {existing_channel.mention}",
                    ephemeral=True,
                )
                return

            self.repository.delete_by_channel_id(existing_ticket.channel_id)

        subject = derive_ticket_subject(ticket_type, submission)
        channel_name = build_ticket_channel_name(
            ticket_type.channel_prefix,
            context.creator.display_name,
            context.creator.id,
        )
        channel: discord.TextChannel | None = None
        try:
            channel = await create_ticket_channel(
                context=context,
                ticket_type=ticket_type,
                channel_name=channel_name,
            )

            created_at = get_utc_time()
            record = self.repository.create_ticket(
                guild_id=context.guild.id,
                channel_id=channel.id,
                creator_id=context.creator.id,
                ticket_type=ticket_type.key,
                panel_type=ticket_type.panel_key,
                subject=subject,
                details=submission,
                status=STATUS_OPEN,
                created_at=created_at,
            )

            from .views.inside import TicketControlView

            control_message = await channel.send(
                content=context.creator.mention,
                embed=self.renderers.build_ticket_embed(record, context.guild),
                view=TicketControlView(self),
            )
            self.repository.set_message_id(channel.id, control_message.id, get_utc_time())

            if ticket_type.attachment_prompt:
                await channel.send(f"📎 {context.creator.mention}, {ticket_type.attachment_prompt}")
        except Exception:
            logger.exception(
                "Не удалось создать тикет типа %s для пользователя %s.",
                ticket_type.key,
                context.creator.id,
            )
            if channel is not None:
                self.repository.delete_by_channel_id(channel.id)
                await delete_ticket_channel(
                    channel,
                    reason="Откат после неудачного создания тикета",
                    logger=logger,
                )

            await safe_followup_send(
                interaction,
                "❌ Не удалось создать тикет. Попробуйте ещё раз или обратитесь к администрации.",
                ephemeral=True,
            )
            return

        await safe_followup_send(
            interaction,
            f"✅ Тикет {channel.mention} создан. В нём уже доступна staff-команда.",
            ephemeral=True,
        )

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

    async def _resolve_creation_context(
        self,
        interaction: discord.Interaction,
        ticket_type: TicketTypeSpec,
    ) -> TicketCreationContext | None:
        guild = interaction.guild
        if guild is None:
            await safe_followup_send(interaction, "❌ Команда доступна только на сервере.", ephemeral=True)
            return None

        if not isinstance(interaction.user, discord.Member):
            await safe_followup_send(interaction, "❌ Не удалось определить участника сервера.", ephemeral=True)
            return None

        guild_settings = self.get_guild_settings(guild.id)
        if guild_settings is None:
            await safe_followup_send(
                interaction,
                "❌ Система тикетов не настроена. Администратор должен выполнить `/tickets settings set`.",
                ephemeral=True,
            )
            return None

        category = guild.get_channel(ticket_type.category_id(guild_settings))
        if not isinstance(category, discord.CategoryChannel):
            await safe_followup_send(
                interaction,
                "❌ Категория для этого типа тикетов не настроена или была удалена.",
                ephemeral=True,
            )
            return None

        staff_role = guild.get_role(guild_settings.support_role_id)
        if staff_role is None:
            await safe_followup_send(interaction, "❌ Staff-роль не найдена.", ephemeral=True)
            return None

        return TicketCreationContext(
            guild=guild,
            creator=interaction.user,
            category=category,
            staff_role=staff_role,
        )

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

    def claim_interaction(self, interaction: discord.Interaction) -> bool:
        interaction_id = getattr(interaction, "id", None)
        if interaction_id is None:
            return True

        if interaction_id in self._active_interaction_ids:
            return False

        self._active_interaction_ids.add(interaction_id)
        return True

    def release_interaction(self, interaction: discord.Interaction) -> None:
        interaction_id = getattr(interaction, "id", None)
        if interaction_id is not None:
            self._active_interaction_ids.discard(interaction_id)

    async def _safe_defer_response(
        self,
        interaction: discord.Interaction,
        *,
        ephemeral: bool = False,
        thinking: bool = False,
    ) -> bool:
        return await safe_defer(interaction, ephemeral=ephemeral, thinking=thinking)

    @staticmethod
    def _is_acknowledged_interaction_error(error: discord.HTTPException) -> bool:
        return is_acknowledged_interaction_error(error)

    def _can_close_ticket(
        self,
        member: discord.Member,
        record: TicketRecord,
        guild_settings: TicketGuildSettings | None,
    ) -> bool:
        return member.id == record.creator_id or self._is_staff(member, guild_settings)

    def _is_staff(self, member: discord.Member, guild_settings: TicketGuildSettings | None) -> bool:
        return member.guild_permissions.manage_channels or (
            guild_settings is not None
            and any(role.id == guild_settings.support_role_id for role in member.roles)
        )
