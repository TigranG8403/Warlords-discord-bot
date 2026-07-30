from __future__ import annotations

import logging
import re
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from core.discord_interactions import safe_defer, safe_followup_send, safe_response_send_message
from core.module import BotModule
from core.panel_registry import PublishedPanelRecord, PublishedPanelRepository
from core.panel_runtime import PanelRenderResult, PanelRuntime
from core.time_of_day import period_key, pick_banner_asset_path
from modules.tickets.banner import make_banner_file
from modules.tickets.config import get_msk_time

from .repository import KompromatRepository
from .service import KompromatService
from .views import KompromatPanelView

logger = logging.getLogger(__name__)
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)

KOMPROMAT_BANNER_FILENAME = "kompromat_banner.png"
KOMPROMAT_BANNER_TEXT = "Compromat"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = PROJECT_ROOT / "assets"
KOMPROMAT_DB_PATH = PROJECT_ROOT / "data" / "kompromat.sqlite3"
PANEL_REGISTRY_DB_PATH = PROJECT_ROOT / "data" / "panel_registry.sqlite3"
KOMPROMAT_PANELS_LEGACY_PATH = PROJECT_ROOT / "data" / "kompromat_panels.json"
KOMPROMAT_COLOR = 0x701F1F


def _build_panel_embed(*, image_url: str | None) -> discord.Embed:
    embed = discord.Embed(
        description=(
            "## 🗂️ **Компроматы**\n\n"
            "Оставляйте короткие записи по спорным ситуациям, нарушениям и игрокам, которые стоит держать под рукой.\n\n"
            "Сначала выберите категорию, затем отметьте участников при необходимости и заполните короткую форму. "
            "Скрины, файлы и ссылки можно спокойно докинуть уже в отдельный тред доказательств."
        ),
        color=KOMPROMAT_COLOR,
    )
    if image_url:
        embed.set_image(url=image_url)
    return embed


async def _safe_followup(interaction: discord.Interaction, message: str, *, interaction_active: bool) -> None:
    if not interaction_active:
        return

    await safe_followup_send(interaction, message, ephemeral=True)


def build_module() -> BotModule:
    repository = KompromatRepository(KOMPROMAT_DB_PATH)
    service = KompromatService(repository)
    panel_repository = PublishedPanelRepository(
        PANEL_REGISTRY_DB_PATH,
        namespace="kompromat",
        legacy_path=KOMPROMAT_PANELS_LEGACY_PATH,
    )

    def render_panel(_record: PublishedPanelRecord, _channel: discord.TextChannel) -> PanelRenderResult:
        banner_file = make_banner_file(
            asset_path=pick_banner_asset_path(
                assets_dir=ASSETS_DIR,
                stem="minecraft",
                current_time=get_msk_time(),
            ),
            text=KOMPROMAT_BANNER_TEXT,
            filename=KOMPROMAT_BANNER_FILENAME,
        )
        image_url = f"attachment://{KOMPROMAT_BANNER_FILENAME}" if banner_file is not None else None
        return PanelRenderResult(
            embed=_build_panel_embed(image_url=image_url),
            view=KompromatPanelView(service),
            files=(banner_file,) if banner_file is not None else (),
        )

    runtime = PanelRuntime(
        name="kompromat",
        repository=panel_repository,
        render_panel=render_panel,
        period_getter=lambda: period_key(get_msk_time()),
        logger=logger,
    )

    def register(bot: commands.Bot) -> None:
        runtime.bind(bot)

        kompromat_group = app_commands.Group(name="kompromat", description="Панель и поиск компроматов")

        @kompromat_group.command(name="panel", description="Опубликовать панель компроматов")
        @app_commands.describe(
            archive_channel="Канал, куда будут складываться записи компроматов.",
            channel="Канал, в который нужно отправить саму панель. Если не указан, используется текущий.",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def publish_panel(
            interaction: discord.Interaction,
            archive_channel: discord.TextChannel,
            channel: discord.TextChannel | None = None,
        ) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=True)

            target_channel = channel or interaction.channel
            if not isinstance(target_channel, discord.TextChannel) or interaction.guild is None:
                await _safe_followup(
                    interaction,
                    "❌ Нужен текстовый канал сервера.",
                    interaction_active=interaction_active,
                )
                return

            repository.set_archive_channel(interaction.guild.id, archive_channel.id)
            await runtime.publish(target_channel, PublishedPanelRecord(channel_id=target_channel.id))

            await _safe_followup(
                interaction,
                f"✅ Панель компроматов отправлена в {target_channel.mention}. Архив: {archive_channel.mention}.",
                interaction_active=interaction_active,
            )

        @kompromat_group.command(name="search", description="Найти компроматы по тегу игрока")
        @app_commands.describe(member="Игрок, по которому нужно показать записи.")
        async def search_entries(interaction: discord.Interaction, member: discord.Member) -> None:
            if interaction.guild is None:
                await safe_response_send_message(
                    interaction,
                    "❌ Команда доступна только на сервере.",
                    ephemeral=True,
                )
                return

            entries = service.search_by_member(guild_id=interaction.guild.id, member=member)
            embed = service.build_search_embed(member=member, entries=entries)
            await safe_response_send_message(interaction, embed=embed, ephemeral=True)

        async def on_message(message: discord.Message) -> None:
            if message.author.bot or not isinstance(message.channel, discord.Thread):
                return

            entry = repository.get_by_thread_id(message.channel.id)
            if entry is None or entry.has_evidence:
                return

            has_material = bool(
                message.attachments
                or message.embeds
                or URL_RE.search(message.content)
                or message.content.strip()
            )
            if not has_material:
                return

            parent = message.channel.parent
            if not isinstance(parent, discord.TextChannel):
                return

            try:
                parent_message = await parent.fetch_message(entry.message_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return

            if not parent_message.embeds:
                repository.mark_has_evidence(entry.entry_id)
                return

            embed = discord.Embed.from_dict(parent_message.embeds[0].to_dict())
            field_index = next(
                (index for index, field in enumerate(embed.fields) if field.name == "Доказательства"),
                None,
            )
            if field_index is None:
                embed.add_field(
                    name="Доказательства",
                    value=f"Добавлены • <#{message.channel.id}>",
                    inline=True,
                )
            else:
                embed.set_field_at(
                    field_index,
                    name="Доказательства",
                    value=f"Добавлены • <#{message.channel.id}>",
                    inline=True,
                )

            try:
                await parent_message.edit(embed=embed)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return

            repository.mark_has_evidence(entry.entry_id)

        bot.tree.add_command(kompromat_group)
        bot.add_listener(on_message, "on_message")

    async def on_ready(bot: commands.Bot) -> None:
        await runtime.on_ready(bot)

    def persistent_views():
        return [KompromatPanelView(service)]

    return BotModule(
        name="kompromat",
        description="Панель компроматов с быстрым поиском по тегам игроков.",
        register=register,
        on_ready=on_ready,
        persistent_views=persistent_views,
    )
