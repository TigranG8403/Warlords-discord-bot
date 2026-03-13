from __future__ import annotations

from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from core.discord_interactions import safe_defer, safe_followup_send
from core.module import BotModule
from core.panel_registry import PublishedPanelRecord, PublishedPanelRepository
from core.panel_runtime import PanelRenderResult, PanelRuntime
from core.time_of_day import period_key, pick_banner_asset_path
from modules.tickets.banner import make_banner_file
from modules.tickets.config import get_msk_time

from .content import (
    BANNER_FILENAME,
    BANNER_TEXT,
    CHANNEL_OPTION_DESCRIPTION,
    COMMAND_DESCRIPTION,
    EMBED_COLOR,
    EMBED_DESCRIPTION,
    GROUP_DESCRIPTION,
    INVALID_CHANNEL_MESSAGE,
    MODULE_DESCRIPTION,
    SUCCESS_MESSAGE,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = PROJECT_ROOT / "assets"
PANEL_REGISTRY_DB_PATH = PROJECT_ROOT / "data" / "panel_registry.sqlite3"
WELCOME_PANELS_LEGACY_PATH = PROJECT_ROOT / "data" / "welcome_panels.json"


def _build_welcome_embed(*, image_url: str | None) -> discord.Embed:
    embed = discord.Embed(description=EMBED_DESCRIPTION, color=EMBED_COLOR)
    if image_url:
        embed.set_image(url=image_url)
    return embed


async def _safe_followup(interaction: discord.Interaction, message: str, *, interaction_active: bool) -> None:
    if not interaction_active:
        return

    await safe_followup_send(interaction, message, ephemeral=True)


def build_module() -> BotModule:
    repository = PublishedPanelRepository(
        PANEL_REGISTRY_DB_PATH,
        namespace="welcome",
        legacy_path=WELCOME_PANELS_LEGACY_PATH,
    )

    def render_panel(_record: PublishedPanelRecord, _channel: discord.TextChannel) -> PanelRenderResult:
        banner_file = make_banner_file(
            asset_path=pick_banner_asset_path(
                assets_dir=ASSETS_DIR,
                stem="minecraft",
                current_time=get_msk_time(),
            ),
            text=BANNER_TEXT,
            filename=BANNER_FILENAME,
        )
        image_url = f"attachment://{BANNER_FILENAME}" if banner_file is not None else None
        return PanelRenderResult(
            embed=_build_welcome_embed(image_url=image_url),
            files=(banner_file,) if banner_file is not None else (),
        )

    runtime = PanelRuntime(
        name="welcome",
        repository=repository,
        render_panel=render_panel,
        period_getter=lambda: period_key(get_msk_time()),
    )

    def register(bot: commands.Bot) -> None:
        runtime.bind(bot)

        welcome_group = app_commands.Group(name="welcome", description=GROUP_DESCRIPTION)

        @welcome_group.command(name="panel", description=COMMAND_DESCRIPTION)
        @app_commands.describe(channel=CHANNEL_OPTION_DESCRIPTION)
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def publish_panel(
            interaction: discord.Interaction,
            channel: discord.TextChannel | None = None,
        ) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=True)

            target_channel = channel or interaction.channel
            if not isinstance(target_channel, discord.TextChannel):
                await _safe_followup(
                    interaction,
                    INVALID_CHANNEL_MESSAGE,
                    interaction_active=interaction_active,
                )
                return

            await runtime.publish(target_channel, PublishedPanelRecord(channel_id=target_channel.id))
            await _safe_followup(
                interaction,
                SUCCESS_MESSAGE.format(channel=target_channel.mention),
                interaction_active=interaction_active,
            )

        bot.tree.add_command(welcome_group)

    async def on_ready(bot: commands.Bot) -> None:
        await runtime.on_ready(bot)

    return BotModule(
        name="welcome",
        description=MODULE_DESCRIPTION,
        register=register,
        on_ready=on_ready,
    )
