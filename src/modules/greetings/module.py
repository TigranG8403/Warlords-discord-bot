from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from core.discord_interactions import safe_defer, safe_followup_send
from core.module import BotModule
from integrations.ai import AiClientConfig, OpenAiCompatibleClient

from .copywriter import GreetingCopywriter
from .models import GreetingsConfig
from .repository import GreetingsRepository
from .service import GreetingsService


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_PATH = PROJECT_ROOT / "data" / "greetings.sqlite3"
ASSETS_DIR = PROJECT_ROOT / "assets"


def _build_ai_client() -> OpenAiCompatibleClient | None:
    try:
        config = AiClientConfig.from_env()
    except (RuntimeError, ValueError) as error:
        logger.error("AI для приветствий отключён из-за ошибки конфигурации: %s", error)
        return None
    if config is None:
        return None

    greeting_config = AiClientConfig(
        base_url=config.base_url,
        model=config.model,
        api_key=config.api_key,
        timeout_seconds=min(config.timeout_seconds, 6.0),
        max_response_bytes=min(config.max_response_bytes, 100_000),
    )
    return OpenAiCompatibleClient(greeting_config)


def _missing_permissions(channel: discord.TextChannel, bot_member: discord.Member) -> list[str]:
    permissions = channel.permissions_for(bot_member)
    required = {
        "view_channel": "View Channel",
        "send_messages": "Send Messages",
        "embed_links": "Embed Links",
        "attach_files": "Attach Files",
    }
    return [label for attribute, label in required.items() if not getattr(permissions, attribute)]


def build_module() -> BotModule:
    repository = GreetingsRepository(DATABASE_PATH)
    ai_client = _build_ai_client()
    copywriter = GreetingCopywriter(ai_client)
    service = GreetingsService(assets_dir=ASSETS_DIR, copywriter=copywriter)

    def register(bot: commands.Bot) -> None:
        greetings_group = app_commands.Group(
            name="greetings",
            description="Управление персональными приветствиями участников",
        )

        @greetings_group.command(
            name="setup",
            description="Включить приветствия в выбранном канале",
        )
        @app_commands.describe(channel="Канал, в который бот будет отправлять приветствия.")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def setup_greetings(
            interaction: discord.Interaction,
            channel: discord.TextChannel,
        ) -> None:
            guild = interaction.guild
            if guild is None or guild.me is None:
                await interaction.response.send_message(
                    "❌ Команда доступна только на сервере.",
                    ephemeral=True,
                )
                return

            missing = _missing_permissions(channel, guild.me)
            if missing:
                await interaction.response.send_message(
                    "❌ В выбранном канале боту не хватает прав: "
                    + ", ".join(f"`{permission}`" for permission in missing)
                    + ".",
                    ephemeral=True,
                )
                return

            repository.set_config(GreetingsConfig(guild_id=guild.id, channel_id=channel.id))
            await interaction.response.send_message(
                f"✅ Приветствия включены в {channel.mention}. Для проверки: `/greetings fake-join`.",
                ephemeral=True,
            )

        @greetings_group.command(
            name="fake-join",
            description="Отправить тестовое приветствие без настоящего входа на сервер",
        )
        @app_commands.describe(
            member="Участник, для которого нужно собрать приветствие. По умолчанию — вы.",
            channel="Канал для теста. По умолчанию — настроенный или текущий.",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        @app_commands.checks.cooldown(1, 10.0, key=lambda interaction: interaction.guild_id)
        async def fake_join(
            interaction: discord.Interaction,
            member: discord.Member | None = None,
            channel: discord.TextChannel | None = None,
        ) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=True)
            guild = interaction.guild
            if not interaction_active or guild is None:
                return

            target_member = member
            if target_member is None and isinstance(interaction.user, discord.Member):
                target_member = interaction.user
            if target_member is None:
                await safe_followup_send(
                    interaction,
                    "❌ Не удалось определить тестового участника.",
                    ephemeral=True,
                )
                return

            config = repository.get_config(guild.id)
            configured_channel = guild.get_channel(config.channel_id) if config is not None else None
            target_channel = channel or (
                configured_channel if isinstance(configured_channel, discord.TextChannel) else None
            )
            if target_channel is None and isinstance(interaction.channel, discord.TextChannel):
                target_channel = interaction.channel
            if not isinstance(target_channel, discord.TextChannel):
                await safe_followup_send(
                    interaction,
                    "❌ Укажите текстовый канал для теста.",
                    ephemeral=True,
                )
                return

            try:
                await service.send_greeting(target_channel, target_member)
            except (discord.Forbidden, discord.HTTPException):
                logger.exception(
                    "Не удалось отправить тестовое приветствие в канал %s.",
                    target_channel.id,
                )
                await safe_followup_send(
                    interaction,
                    "❌ Не удалось отправить приветствие. Проверьте права бота в канале.",
                    ephemeral=True,
                )
                return

            await safe_followup_send(
                interaction,
                f"✅ Фейковое присоединение отправлено в {target_channel.mention}.",
                ephemeral=True,
            )

        @greetings_group.command(
            name="status",
            description="Показать канал автоматических приветствий",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def greetings_status(interaction: discord.Interaction) -> None:
            guild = interaction.guild
            config = repository.get_config(guild.id) if guild is not None else None
            if config is None or guild is None:
                await interaction.response.send_message(
                    "ℹ️ Автоматические приветствия не настроены.",
                    ephemeral=True,
                )
                return

            channel = guild.get_channel(config.channel_id)
            channel_label = channel.mention if channel is not None else f"`{config.channel_id}` (не найден)"
            ai_status = "включены" if ai_client is not None else "недоступны, используется fallback"
            await interaction.response.send_message(
                f"## Приветствия включены\nКанал: {channel_label}\nAI-реплики: **{ai_status}**",
                ephemeral=True,
            )

        @greetings_group.command(
            name="disable",
            description="Отключить автоматические приветствия",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def disable_greetings(interaction: discord.Interaction) -> None:
            guild = interaction.guild
            if guild is None or repository.get_config(guild.id) is None:
                await interaction.response.send_message(
                    "ℹ️ Автоматические приветствия уже отключены.",
                    ephemeral=True,
                )
                return

            repository.delete_config(guild.id)
            await interaction.response.send_message(
                "✅ Автоматические приветствия отключены. Старые сообщения сохранены.",
                ephemeral=True,
            )

        async def on_member_join(member: discord.Member) -> None:
            if member.bot:
                return

            config = repository.get_config(member.guild.id)
            if config is None:
                return

            channel = member.guild.get_channel(config.channel_id)
            if not isinstance(channel, discord.TextChannel):
                logger.warning(
                    "Канал приветствий %s на сервере %s не найден.",
                    config.channel_id,
                    member.guild.id,
                )
                return

            try:
                await service.send_greeting(channel, member)
            except (discord.Forbidden, discord.HTTPException):
                logger.exception(
                    "Не удалось приветствовать участника %s на сервере %s.",
                    member.id,
                    member.guild.id,
                )

        bot.tree.add_command(greetings_group)
        bot.add_listener(on_member_join, "on_member_join")

    return BotModule(
        name="greetings",
        description="Персональные приветствия новых участников с локальным баннером.",
        register=register,
    )
