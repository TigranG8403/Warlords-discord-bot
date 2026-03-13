from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from core.discord_interactions import safe_defer, safe_followup_send
from core.module import BotModule
from core.panel_registry import PublishedPanelRecord, PublishedPanelRepository
from core.panel_runtime import PanelRenderResult, PanelRuntime
from core.time_of_day import period_key

from .banner import make_banner_file
from .catalog import ROOT_PANEL, get_panel
from .config import (
    TicketGuildSettings,
    get_msk_time,
    get_panel_banner_asset_path,
    load_tickets_settings,
)
from .service import TicketService
from .views import TicketControlView, TicketPanelView, build_panel_embed

logger = logging.getLogger(__name__)

PANEL_BANNER_TEXT = "Tickets"
PANEL_BANNER_FILENAME = "panel_banner.png"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PANEL_REGISTRY_DB_PATH = PROJECT_ROOT / "data" / "panel_registry.sqlite3"
TICKET_PANELS_LEGACY_PATH = PROJECT_ROOT / "data" / "ticket_panels.json"


async def _safe_followup(interaction: discord.Interaction, message: str, *, interaction_active: bool) -> None:
    if not interaction_active:
        return

    await safe_followup_send(interaction, message, ephemeral=True)


def _resolve_bot_member(bot: commands.Bot, guild: discord.Guild) -> discord.Member | None:
    if bot.user is None:
        return None
    return guild.get_member(bot.user.id)


def _format_settings_summary(guild: discord.Guild, settings: TicketGuildSettings) -> str:
    support_role = guild.get_role(settings.support_role_id)
    log_channel = guild.get_channel(settings.log_channel_id)
    ticket_category = guild.get_channel(settings.ticket_category_id)
    fraction_category = guild.get_channel(settings.fraction_category_id)
    rp_category = guild.get_channel(settings.rp_category_id)

    def describe_channel(channel: discord.abc.GuildChannel | None, fallback_id: int) -> str:
        if channel is None:
            return f"`{fallback_id}` (не найден)"
        if isinstance(channel, discord.CategoryChannel):
            return f"`{channel.name}` (`{channel.id}`)"
        return channel.mention

    support_role_label = support_role.mention if support_role is not None else f"`{settings.support_role_id}` (не найдена)"
    return "\n".join(
        (
            f"staff role: {support_role_label}",
            f"log channel: {describe_channel(log_channel, settings.log_channel_id)}",
            f"ticket category: {describe_channel(ticket_category, settings.ticket_category_id)}",
            f"fraction category: {describe_channel(fraction_category, settings.fraction_category_id)}",
            f"rp category: {describe_channel(rp_category, settings.rp_category_id)}",
            f"staff cooldown: {settings.staff_call_cooldown_minutes} min",
        )
    )


def _format_validation_issues(issues: list[str]) -> str:
    if not issues:
        return "✅ Проверка пройдена: настройки выглядят корректно."
    return "\n".join(["⚠️ Найдены проблемы:"] + [f"- {issue}" for issue in issues])


def build_module() -> BotModule:
    settings = load_tickets_settings()
    service = TicketService(settings)
    repository = PublishedPanelRepository(
        PANEL_REGISTRY_DB_PATH,
        namespace="tickets",
        legacy_path=TICKET_PANELS_LEGACY_PATH,
    )
    panel_spec = get_panel(ROOT_PANEL)

    def render_panel(_record: PublishedPanelRecord, _channel: discord.TextChannel) -> PanelRenderResult:
        banner_file = make_banner_file(
            asset_path=get_panel_banner_asset_path(),
            text=PANEL_BANNER_TEXT,
            filename=PANEL_BANNER_FILENAME,
        )
        image_url = f"attachment://{PANEL_BANNER_FILENAME}" if banner_file is not None else None
        return PanelRenderResult(
            embed=build_panel_embed(
                panel=panel_spec,
                image_url=image_url,
                color=panel_spec.color(settings),
            ),
            view=TicketPanelView(service),
            files=(banner_file,) if banner_file is not None else (),
        )

    runtime = PanelRuntime(
        name="tickets",
        repository=repository,
        render_panel=render_panel,
        period_getter=lambda: period_key(get_msk_time()),
        logger=logger,
    )

    def register(bot: commands.Bot) -> None:
        runtime.bind(bot)

        tickets_group = app_commands.Group(name="tickets", description="Управление тикет-системой")
        settings_group = app_commands.Group(name="settings", description="Настройка тикет-системы")

        @tickets_group.command(name="panel", description="Опубликовать общую панель тикетов")
        @app_commands.describe(
            channel="Канал, в который нужно отправить панель. Если не указан, используется текущий.",
        )
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
                    "❌ Нужен текстовый канал сервера.",
                    interaction_active=interaction_active,
                )
                return

            guild_settings = service.get_guild_settings(target_channel.guild.id)
            if guild_settings is None:
                await _safe_followup(
                    interaction,
                    "❌ Сначала настройте модуль через `/tickets settings set`.",
                    interaction_active=interaction_active,
                )
                return

            validation_issues = service.validate_guild_settings(
                target_channel.guild,
                guild_settings,
                bot_member=_resolve_bot_member(bot, target_channel.guild),
            )
            if validation_issues:
                await _safe_followup(
                    interaction,
                    "❌ Панель не опубликована, потому что настройки сейчас некорректны.\n"
                    f"{_format_validation_issues(validation_issues)}",
                    interaction_active=interaction_active,
                )
                return

            await runtime.publish(target_channel, PublishedPanelRecord(channel_id=target_channel.id))

            await _safe_followup(
                interaction,
                f"✅ Общая панель тикетов отправлена в {target_channel.mention}.",
                interaction_active=interaction_active,
            )

        @settings_group.command(name="set", description="Сохранить настройки тикет-системы для сервера")
        @app_commands.describe(
            support_role="Роль staff, которая получает доступ к тикетам.",
            log_channel="Канал, куда отправлять логи закрытых тикетов.",
            ticket_category="Категория для обычных тикетов.",
            fraction_category="Категория для тикетов рекламы фракций.",
            rp_category="Категория для RP-тикетов.",
            staff_call_cooldown_minutes="Сколько минут ждать между вызовами staff в одном тикете.",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def set_settings(
            interaction: discord.Interaction,
            support_role: discord.Role,
            log_channel: discord.TextChannel,
            ticket_category: discord.CategoryChannel,
            fraction_category: discord.CategoryChannel,
            rp_category: discord.CategoryChannel,
            staff_call_cooldown_minutes: app_commands.Range[int, 1, 120] = 5,
        ) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=True)

            guild = interaction.guild
            if guild is None:
                await _safe_followup(
                    interaction,
                    "❌ Команда доступна только на сервере.",
                    interaction_active=interaction_active,
                )
                return

            guild_settings = TicketGuildSettings(
                guild_id=guild.id,
                ticket_category_id=ticket_category.id,
                fraction_category_id=fraction_category.id,
                rp_category_id=rp_category.id,
                log_channel_id=log_channel.id,
                support_role_id=support_role.id,
                staff_call_cooldown_minutes=staff_call_cooldown_minutes,
            )
            service.set_guild_settings(guild_settings)

            validation_issues = service.validate_guild_settings(
                guild,
                guild_settings,
                bot_member=_resolve_bot_member(bot, guild),
            )
            message = (
                "✅ Настройки тикет-системы сохранены.\n"
                f"{_format_settings_summary(guild, guild_settings)}\n\n"
                f"{_format_validation_issues(validation_issues)}"
            )
            await _safe_followup(interaction, message, interaction_active=interaction_active)

        @settings_group.command(name="show", description="Показать текущие настройки тикет-системы")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def show_settings(interaction: discord.Interaction) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=False)

            guild = interaction.guild
            if guild is None:
                await _safe_followup(
                    interaction,
                    "❌ Команда доступна только на сервере.",
                    interaction_active=interaction_active,
                )
                return

            guild_settings = service.get_guild_settings(guild.id)
            if guild_settings is None:
                await _safe_followup(
                    interaction,
                    "ℹ️ Настройки тикет-системы ещё не заданы. Используйте `/tickets settings set`.",
                    interaction_active=interaction_active,
                )
                return

            await _safe_followup(
                interaction,
                "Текущие настройки тикет-системы:\n" + _format_settings_summary(guild, guild_settings),
                interaction_active=interaction_active,
            )

        @settings_group.command(name="validate", description="Проверить, что настройки тикет-системы ещё валидны")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def validate_settings(interaction: discord.Interaction) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=False)

            guild = interaction.guild
            if guild is None:
                await _safe_followup(
                    interaction,
                    "❌ Команда доступна только на сервере.",
                    interaction_active=interaction_active,
                )
                return

            guild_settings = service.get_guild_settings(guild.id)
            if guild_settings is None:
                await _safe_followup(
                    interaction,
                    "ℹ️ Настройки тикет-системы ещё не заданы. Используйте `/tickets settings set`.",
                    interaction_active=interaction_active,
                )
                return

            validation_issues = service.validate_guild_settings(
                guild,
                guild_settings,
                bot_member=_resolve_bot_member(bot, guild),
            )
            await _safe_followup(
                interaction,
                f"{_format_settings_summary(guild, guild_settings)}\n\n{_format_validation_issues(validation_issues)}",
                interaction_active=interaction_active,
            )

        tickets_group.add_command(settings_group)
        bot.tree.add_command(tickets_group)

    async def on_ready(bot: commands.Bot) -> None:
        await runtime.on_ready(bot)

    def persistent_views():
        return [TicketPanelView(service), TicketControlView(service)]

    return BotModule(
        name="tickets",
        description="Система тикетов на slash-командах и модалках.",
        register=register,
        on_ready=on_ready,
        persistent_views=persistent_views,
    )
