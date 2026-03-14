from __future__ import annotations

import discord
from discord.ui import Button, Modal, TextInput, View

from core.discord_interactions import safe_response_send_message, safe_response_send_modal

from ..service import TicketService


async def _safe_send_message(interaction: discord.Interaction, message: str) -> bool:
    return await safe_response_send_message(interaction, message, ephemeral=True)


async def _safe_send_modal(interaction: discord.Interaction, modal: Modal) -> bool:
    return await safe_response_send_modal(interaction, modal)


class CloseReasonModal(Modal):
    def __init__(self, service: TicketService):
        super().__init__(title="Закрытие тикета")
        self.service = service
        self.reason = TextInput(
            label="Причина закрытия",
            placeholder="Например: вопрос решен / заявка обработана / недостаточно данных",
            style=discord.TextStyle.paragraph,
            max_length=500,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        reason = self.reason.value.strip()
        if not reason:
            await _safe_send_message(interaction, "❌ Укажите причину закрытия тикета.")
            return

        await self.service.close_ticket(interaction, reason)


class TicketControlView(View):
    def __init__(self, service: TicketService):
        super().__init__(timeout=None)
        self.service = service

        call_staff_button = Button(
            label="Позвать staff",
            style=discord.ButtonStyle.primary,
            emoji="🔔",
            custom_id="ticket_call_staff",
            row=0,
        )
        call_staff_button.callback = self._call_staff
        self.add_item(call_staff_button)

        claim_button = Button(
            label="Взять в работу",
            style=discord.ButtonStyle.secondary,
            emoji="🛠️",
            custom_id="ticket_claim",
            row=0,
        )
        claim_button.callback = self._claim_ticket
        self.add_item(claim_button)

        waiting_button = Button(
            label="Ожидаем игрока",
            style=discord.ButtonStyle.secondary,
            emoji="⌛",
            custom_id="ticket_waiting_user",
            row=1,
        )
        waiting_button.callback = self._mark_waiting_user
        self.add_item(waiting_button)

        close_button = Button(
            label="Закрыть тикет",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id="ticket_close",
            row=1,
        )
        close_button.callback = self._open_close_modal
        self.add_item(close_button)

    async def _call_staff(self, interaction: discord.Interaction) -> None:
        await self.service.call_staff(interaction)

    async def _claim_ticket(self, interaction: discord.Interaction) -> None:
        await self.service.claim_ticket(interaction)

    async def _mark_waiting_user(self, interaction: discord.Interaction) -> None:
        await self.service.mark_waiting_user(interaction)

    async def _open_close_modal(self, interaction: discord.Interaction) -> None:
        record = None
        if isinstance(interaction.channel, discord.TextChannel):
            record = self.service.repository.get_by_channel_id(interaction.channel.id)

        if record is None:
            await _safe_send_message(interaction, "⚠️ Для этого канала не найден тикет.")
            return

        if not isinstance(interaction.user, discord.Member):
            await _safe_send_message(interaction, "❌ Не удалось определить участника сервера.")
            return

        guild = getattr(interaction, "guild", None)
        guild_settings = self.service.get_guild_settings(guild.id) if guild is not None else None

        if not self.service._can_close_ticket(interaction.user, record, guild_settings):
            await _safe_send_message(interaction, "❌ У вас нет прав для закрытия этого тикета.")
            return

        await _safe_send_modal(interaction, CloseReasonModal(self.service))
