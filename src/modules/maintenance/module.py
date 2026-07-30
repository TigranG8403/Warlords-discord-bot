from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from core.discord_interactions import safe_defer, safe_followup_send, safe_response_send_message
from core.module import BotModule

from .access import load_allowed_user_ids
from .deployment import DeploymentController, DeploymentError


logger = logging.getLogger(__name__)


def build_module() -> BotModule:
    allowed_user_ids = load_allowed_user_ids()
    deployment = DeploymentController()

    def register(bot: commands.Bot) -> None:
        bot_group = app_commands.Group(
            name="bot",
            description="Служебные команды Warlords Bot",
        )

        @bot_group.command(
            name="update",
            description="Проверить и безопасно установить последнюю версию бота",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def update_bot(interaction: discord.Interaction) -> None:
            if interaction.user.id not in allowed_user_ids:
                await safe_response_send_message(
                    interaction,
                    "❌ Эта команда доступна только владельцам деплоя.",
                    ephemeral=True,
                )
                return

            interaction_active = await safe_defer(
                interaction,
                ephemeral=True,
                thinking=True,
            )
            if not interaction_active:
                return

            try:
                await deployment.trigger_update()
            except DeploymentError as error:
                logger.warning(
                    "Пользователь %s не смог запустить обновление: %s",
                    interaction.user.id,
                    error,
                )
                await safe_followup_send(interaction, f"⚠️ {error}", ephemeral=True)
                return

            logger.info("Пользователь %s запустил обновление бота.", interaction.user.id)
            await safe_followup_send(
                interaction,
                "✅ Обновление поставлено в очередь. Бот перезапустится только после успешных тестов.",
                ephemeral=True,
            )

        bot.tree.add_command(bot_group)

    return BotModule(
        name="maintenance",
        description="Безопасный запуск атомарного обновления из Discord.",
        register=register,
    )
