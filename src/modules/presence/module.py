from __future__ import annotations

import discord
from discord.ext import commands

from core.module import BotModule


def _members_label(count: int) -> str:
    last_two_digits = count % 100
    last_digit = count % 10

    if 11 <= last_two_digits <= 14:
        return "участников"
    if last_digit == 1:
        return "участник"
    if 2 <= last_digit <= 4:
        return "участника"
    return "участников"


def build_module() -> BotModule:
    async def on_ready(bot: commands.Bot) -> None:
        members = 0
        for guild in bot.guilds:
            guild_members = guild.member_count or 0
            members += max(guild_members - 1, 0)

        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{members} {_members_label(members)}",
            )
        )

    def register(_bot: commands.Bot) -> None:
        return None

    return BotModule(
        name="presence",
        description="Обновляет presence бота при запуске.",
        register=register,
        on_ready=on_ready,
    )
