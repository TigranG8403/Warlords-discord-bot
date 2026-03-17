from __future__ import annotations

import discord

from .config import TicketGuildSettings


class TicketServiceAdminMixin:
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
