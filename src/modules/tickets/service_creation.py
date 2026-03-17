from __future__ import annotations

import logging

import discord

from core.discord_interactions import safe_followup_send

from .catalog import STATUS_OPEN, TicketTypeSpec
from .channel_ops import TicketCreationContext, build_ticket_channel_name, create_ticket_channel, delete_ticket_channel, derive_ticket_subject
from .config import get_utc_time


logger = logging.getLogger(__name__)


class TicketServiceCreationMixin:
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
