from __future__ import annotations

import discord

from core.discord_interactions import is_acknowledged_interaction_error, safe_defer

from .config import TicketGuildSettings
from .repository import TicketRecord


class TicketServiceInteractionMixin:
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
