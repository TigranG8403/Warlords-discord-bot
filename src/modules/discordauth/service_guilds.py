from __future__ import annotations

import discord

from .config import DiscordAuthGuildSettings


class DiscordAuthGuildSettingsMixin:
    def set_guild_settings(self, settings: DiscordAuthGuildSettings) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO guild_settings (
                    guild_id,
                    verify_role_id,
                    start_message_channel_id,
                    admin_command_channel_id,
                    admin_command_role_id,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    verify_role_id = excluded.verify_role_id,
                    start_message_channel_id = excluded.start_message_channel_id,
                    admin_command_channel_id = excluded.admin_command_channel_id,
                    admin_command_role_id = excluded.admin_command_role_id,
                    updated_at = excluded.updated_at
                """,
                (
                    settings.guild_id,
                    settings.verify_role_id,
                    settings.start_message_channel_id,
                    settings.admin_command_channel_id,
                    settings.admin_command_role_id,
                    self._now(),
                ),
            )

    def get_guild_settings(self, guild_id: int) -> DiscordAuthGuildSettings | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT guild_id, verify_role_id, start_message_channel_id, admin_command_channel_id, admin_command_role_id
                FROM guild_settings
                WHERE guild_id = ?
                """,
                (guild_id,),
            ).fetchone()
        if row is None:
            return None
        return DiscordAuthGuildSettings(
            guild_id=int(row["guild_id"]),
            verify_role_id=int(row["verify_role_id"]),
            start_message_channel_id=int(row["start_message_channel_id"]),
            admin_command_channel_id=int(row["admin_command_channel_id"]),
            admin_command_role_id=int(row["admin_command_role_id"]),
        )

    def list_guild_settings(self) -> list[DiscordAuthGuildSettings]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT guild_id, verify_role_id, start_message_channel_id, admin_command_channel_id, admin_command_role_id
                FROM guild_settings
                ORDER BY updated_at DESC, guild_id ASC
                """
            ).fetchall()
        return [
            DiscordAuthGuildSettings(
                guild_id=int(row["guild_id"]),
                verify_role_id=int(row["verify_role_id"]),
                start_message_channel_id=int(row["start_message_channel_id"]),
                admin_command_channel_id=int(row["admin_command_channel_id"]),
                admin_command_role_id=int(row["admin_command_role_id"]),
            )
            for row in rows
        ]

    def get_primary_guild_settings(self) -> DiscordAuthGuildSettings | None:
        settings = self.list_guild_settings()
        return settings[0] if settings else None

    async def validate_guild_settings(
        self,
        guild: discord.Guild,
        settings: DiscordAuthGuildSettings,
        *,
        bot_member: discord.Member | None,
    ) -> list[str]:
        issues: list[str] = []
        verify_role = guild.get_role(settings.verify_role_id)
        admin_role = guild.get_role(settings.admin_command_role_id)

        if verify_role is None:
            issues.append(f"роль verify `{settings.verify_role_id}` не найдена")
        if admin_role is None:
            issues.append(f"роль админ-команд `{settings.admin_command_role_id}` не найдена")

        return issues
