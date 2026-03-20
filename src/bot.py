from __future__ import annotations

import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from core.bootstrap import ModuleBootstrapper
from core.discord_interactions import is_ignorable_interaction_error, safe_send_ephemeral
from modules import get_modules


BASE_DIR = Path(__file__).resolve().parent


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Требуется переменная окружения {name}.")
    return value


def _parse_optional_int_env(name: str) -> int | None:
    raw_value = os.getenv(name)
    if not raw_value:
        return None
    return int(raw_value)


def _build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.members = True
    intents.messages = True
    intents.message_content = True
    return intents


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


class WarlordsBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            help_command=None,
            intents=_build_intents(),
        )
        self.logger = logging.getLogger(__name__)
        self.bootstrapper = ModuleBootstrapper(
            bot=self,
            modules=get_modules(os.getenv("ENABLED_MODULES")),
        )

    async def setup_hook(self) -> None:
        self.bootstrapper.register_all()

        guild_id = _parse_optional_int_env("APP_COMMAND_GUILD_ID")
        if guild_id is None:
            global_commands = await self.tree.sync()
            self.logger.info("Синхронизировано %s глобальных slash-команд.", len(global_commands))
            return

        guild = discord.Object(id=guild_id)
        self.tree.copy_global_to(guild=guild)
        guild_commands = await self.tree.sync(guild=guild)
        self.tree.clear_commands(guild=None)
        cleared_global_commands = await self.tree.sync()
        self.logger.info(
            "Синхронизировано %s slash-команд для сервера %s.",
            len(guild_commands),
            guild_id,
        )
        self.logger.info("Глобальные slash-команды очищены: %s.", len(cleared_global_commands))

    async def on_ready(self) -> None:
        await self.bootstrapper.dispatch_on_ready()
        self.logger.info("Бот готов к работе.")


load_dotenv(dotenv_path=BASE_DIR / ".env")
_configure_logging()

bot = WarlordsBot()


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    original_error = getattr(error, "original", error)
    command_name = interaction.command.qualified_name if interaction.command is not None else "<unknown>"

    if isinstance(error, app_commands.MissingPermissions):
        message = "❌ Для этой команды нужны права администратора."
    elif isinstance(error, app_commands.CommandOnCooldown):
        message = f"⏱ Команда временно недоступна. Попробуйте через {error.retry_after:.0f} сек."
    elif is_ignorable_interaction_error(original_error):
        return
    else:
        logging.getLogger(__name__).exception("Ошибка slash-команды %s", command_name, exc_info=error)
        message = "⚠️ Не удалось выполнить команду. Подробности уже записаны в лог."

    await safe_send_ephemeral(interaction, message)


@bot.event
async def on_command_error(_ctx: commands.Context[commands.Bot], error: commands.CommandError) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    logging.getLogger(__name__).exception("Ошибка текстовой команды", exc_info=error)


bot.run(_require_env("DISCORD_TOKEN"))
