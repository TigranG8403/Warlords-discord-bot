from __future__ import annotations

import discord

from core.discord_interactions import safe_defer

from .bridge_shared import (
    describe_inactive_login_request,
    finalize_login_interaction,
)
from .service import DiscordAuthService


class ManagedLoginApprovalView(discord.ui.View):
    def __init__(self, service: DiscordAuthService, session_id: str) -> None:
        super().__init__(timeout=120)
        self.service = service
        self.session_id = session_id

    async def _resolve(
        self,
        interaction: discord.Interaction,
        *,
        status: str,
        success_message: str,
    ) -> None:
        interaction_active = await safe_defer(interaction, thinking=False)
        current = self.service.get_login_session(self.session_id)
        if current is None or current.status != "PENDING":
            await finalize_login_interaction(
                interaction,
                content=describe_inactive_login_request(current.status if current is not None else None),
                interaction_active=interaction_active,
            )
            return

        session = self.service.resolve_login_session(self.session_id, status)
        if session is None:
            await finalize_login_interaction(
                interaction,
                content=describe_inactive_login_request(current.status),
                interaction_active=interaction_active,
            )
            return

        await finalize_login_interaction(
            interaction,
            content=success_message,
            interaction_active=interaction_active,
        )

    @discord.ui.button(label="Подтвердить", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._resolve(
            interaction,
            status="APPROVED",
            success_message="Вход подтверждён.",
        )

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._resolve(
            interaction,
            status="DENIED",
            success_message="Вход отклонён.",
        )
