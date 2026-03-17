from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from core.discord_interactions import safe_defer
from core.module import BotModule
from core.panel_registry import PublishedPanelRecord, PublishedPanelRepository
from core.panel_runtime import PanelRenderResult, PanelRuntime
from core.time_of_day import period_key
from modules.tickets.banner import make_banner_file
from modules.tickets.config import get_msk_time

from .bridge import BridgeRuntime
from .config import get_panel_banner_asset_path
from .module_support import (
    DiscordAuthPanelView,
    _build_panel_embed,
    _build_player_choice_name,
    _ensure_admin_command_access,
    _extract_link_code_from_message,
    _format_player_target,
    _format_settings_summary,
    _format_validation_issues,
    _resolve_bot_member,
    _resolve_link_response,
    _resolve_player_query,
    _safe_followup,
)
from .service import DiscordAuthService

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PANEL_REGISTRY_DB_PATH = PROJECT_ROOT / "data" / "panel_registry.sqlite3"
PANEL_LEGACY_PATH = PROJECT_ROOT / "data" / "discordauth_panels.json"
PANEL_BANNER_TEXT = "Account Link"
PANEL_BANNER_FILENAME = "discordauth_banner.png"


def build_module() -> BotModule:
    service = DiscordAuthService()
    bridge = BridgeRuntime(service)
    repository = PublishedPanelRepository(
        PANEL_REGISTRY_DB_PATH,
        namespace="discordauth",
        legacy_path=PANEL_LEGACY_PATH,
    )

    def render_panel(_record: PublishedPanelRecord, _channel: discord.TextChannel) -> PanelRenderResult:
        banner_file = make_banner_file(
            asset_path=get_panel_banner_asset_path(),
            text=PANEL_BANNER_TEXT,
            filename=PANEL_BANNER_FILENAME,
        )
        image_url = f"attachment://{PANEL_BANNER_FILENAME}" if banner_file is not None else None
        return PanelRenderResult(
            embed=_build_panel_embed(image_url=image_url),
            view=DiscordAuthPanelView(service),
            files=(banner_file,) if banner_file is not None else (),
        )

    runtime = PanelRuntime(
        name="discordauth",
        repository=repository,
        render_panel=render_panel,
        period_getter=lambda: period_key(get_msk_time()),
        logger=logger,
    )

    def register(bot: commands.Bot) -> None:
        runtime.bind(bot)

        discordauth_group = app_commands.Group(name="discordauth", description="Управление DiscordAuth")
        settings_group = app_commands.Group(name="settings", description="Настройка DiscordAuth")

        async def player_autocomplete(
            interaction: discord.Interaction,
            current: str,
        ) -> list[app_commands.Choice[str]]:
            if interaction.guild is None:
                return []

            lowered = current.strip().casefold()
            choices: list[app_commands.Choice[str]] = []
            for record in service.list_players():
                haystacks = (
                    record.player_name.casefold(),
                    record.player_uuid.casefold(),
                    str(record.discord_user_id),
                )
                if lowered and not any(lowered in haystack for haystack in haystacks):
                    continue
                choices.append(app_commands.Choice(name=_build_player_choice_name(record), value=record.player_uuid))
                if len(choices) >= 25:
                    break
            return choices

        async def on_private_message(message: discord.Message) -> None:
            if message.author.bot or message.guild is not None:
                return

            code = _extract_link_code_from_message(message.content)
            if code is None:
                return

            if code == "":
                await message.reply(
                    "Пришли код привязки в формате `link ABC123`.",
                    mention_author=False,
                )
                return

            _ok, response = _resolve_link_response(service, message.author, code)
            await message.reply(response, mention_author=False)

        @discordauth_group.command(name="panel", description="Опубликовать DiscordAuth-панель")
        @app_commands.describe(channel="Канал, куда нужно отправить панель.")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def publish_panel(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=True)

            guild = interaction.guild
            if guild is None:
                await _safe_followup(interaction, "❌ Команда доступна только на сервере.", interaction_active=interaction_active)
                return

            settings = service.get_guild_settings(guild.id)
            if settings is None:
                await _safe_followup(
                    interaction,
                    "❌ Сначала задай настройки через `/discordauth settings set`.",
                    interaction_active=interaction_active,
                )
                return

            issues = await service.validate_guild_settings(
                guild,
                settings,
                bot_member=_resolve_bot_member(bot, guild),
            )
            if issues:
                await _safe_followup(
                    interaction,
                    "❌ Панель не опубликована, потому что настройки сейчас некорректны.\n"
                    f"{_format_validation_issues(issues)}",
                    interaction_active=interaction_active,
                )
                return

            bot_member = _resolve_bot_member(bot, guild)
            if bot_member is not None:
                permissions = channel.permissions_for(bot_member)
                channel_issues: list[str] = []
                if not permissions.send_messages:
                    channel_issues.append(f"бот не может писать в {channel.mention}")
                if not permissions.attach_files:
                    channel_issues.append(f"бот не может прикреплять баннеры в {channel.mention}")
                if channel_issues:
                    await _safe_followup(
                        interaction,
                        "❌ Панель не опубликована.\n" + _format_validation_issues(channel_issues),
                        interaction_active=interaction_active,
                    )
                    return

            await runtime.publish(channel, PublishedPanelRecord(channel_id=channel.id))
            await _safe_followup(
                interaction,
                f"✅ DiscordAuth-панель отправлена в {channel.mention}.",
                interaction_active=interaction_active,
            )

        @discordauth_group.command(name="ban", description="Закрыть доступ игроку через DiscordAuth")
        @app_commands.describe(
            player="Игрок из базы DiscordAuth: ник или UUID.",
            reason="Причина блокировки.",
        )
        @app_commands.autocomplete(player=player_autocomplete)
        async def ban_player(interaction: discord.Interaction, player: str, reason: str) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=True)

            context = await _ensure_admin_command_access(service, interaction, interaction_active=interaction_active)
            if context is None:
                return

            record, error_message = _resolve_player_query(service, player)
            if record is None:
                await _safe_followup(interaction, error_message or "❌ Игрок не найден.", interaction_active=interaction_active)
                return

            updated = service.ban_player(record.player_uuid, reason=reason)
            if updated is None:
                await _safe_followup(interaction, "❌ Не удалось выдать бан.", interaction_active=interaction_active)
                return

            await _safe_followup(
                interaction,
                f"⛔ {_format_player_target(updated)} получил пермабан.\nПричина: {updated.admin_note or reason.strip()}",
                interaction_active=interaction_active,
            )

        @discordauth_group.command(name="unlink", description="Снять привязку DiscordAuth у игрока")
        @app_commands.describe(
            player="Игрок из базы DiscordAuth: ник или UUID.",
        )
        @app_commands.autocomplete(player=player_autocomplete)
        async def unlink_player(interaction: discord.Interaction, player: str) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=True)

            context = await _ensure_admin_command_access(service, interaction, interaction_active=interaction_active)
            if context is None:
                return

            record, error_message = _resolve_player_query(service, player)
            if record is None:
                await _safe_followup(interaction, error_message or "❌ Игрок не найден.", interaction_active=interaction_active)
                return

            if not record.linked:
                await _safe_followup(
                    interaction,
                    f"ℹ️ {_format_player_target(record)} уже не привязан к Discord.",
                    interaction_active=interaction_active,
                )
                return

            try:
                updated = service.unlink_player(record.player_uuid)
            except Exception:
                logger.exception("Не удалось снять привязку DiscordAuth для %s (%s).", record.player_name, record.player_uuid)
                await _safe_followup(
                    interaction,
                    "❌ Не удалось снять привязку. Подробности уже записаны в лог.",
                    interaction_active=interaction_active,
                )
                return

            if updated is None:
                await _safe_followup(interaction, "❌ Не удалось снять привязку.", interaction_active=interaction_active)
                return

            await _safe_followup(
                interaction,
                f"✅ Привязка для {_format_player_target(updated)} снята.",
                interaction_active=interaction_active,
            )

        @discordauth_group.command(name="tempban", description="Выдать временный бан через DiscordAuth")
        @app_commands.describe(
            player="Игрок из базы DiscordAuth: ник или UUID.",
            minutes="Срок блокировки в минутах.",
            reason="Причина блокировки.",
        )
        @app_commands.autocomplete(player=player_autocomplete)
        async def temp_ban_player(
            interaction: discord.Interaction,
            player: str,
            minutes: app_commands.Range[int, 1, 43200],
            reason: str,
        ) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=True)

            context = await _ensure_admin_command_access(service, interaction, interaction_active=interaction_active)
            if context is None:
                return

            record, error_message = _resolve_player_query(service, player)
            if record is None:
                await _safe_followup(interaction, error_message or "❌ Игрок не найден.", interaction_active=interaction_active)
                return

            updated = service.apply_temp_ban(record.player_uuid, minutes=minutes, reason=reason)
            if updated is None:
                await _safe_followup(interaction, "❌ Не удалось выдать временный бан.", interaction_active=interaction_active)
                return

            await _safe_followup(
                interaction,
                f"⏳ {_format_player_target(updated)} получил темпбан до <t:{updated.temp_ban_until}:F>.\n"
                f"Причина: {updated.temp_ban_reason or reason.strip()}",
                interaction_active=interaction_active,
            )

        @settings_group.command(name="set", description="Сохранить настройки DiscordAuth для сервера")
        @app_commands.describe(
            verify_role="Роль, которая даёт доступ к серверу.",
            admin_command_role="Роль, которой разрешены админ-команды DiscordAuth.",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def set_settings(
            interaction: discord.Interaction,
            verify_role: discord.Role,
            admin_command_role: discord.Role,
        ) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=True)

            guild = interaction.guild
            if guild is None:
                await _safe_followup(interaction, "❌ Команда доступна только на сервере.", interaction_active=interaction_active)
                return

            settings = DiscordAuthGuildSettings(
                guild_id=guild.id,
                verify_role_id=verify_role.id,
                start_message_channel_id=0,
                admin_command_channel_id=0,
                admin_command_role_id=admin_command_role.id,
            )
            service.set_guild_settings(settings)
            issues = await service.validate_guild_settings(guild, settings, bot_member=_resolve_bot_member(bot, guild))

            await _safe_followup(
                interaction,
                "✅ Настройки DiscordAuth сохранены.\n"
                f"{_format_settings_summary(guild, settings)}\n\n"
                f"{_format_validation_issues(issues)}",
                interaction_active=interaction_active,
            )

        @settings_group.command(name="show", description="Показать текущие настройки DiscordAuth")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def show_settings(interaction: discord.Interaction) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=False)

            guild = interaction.guild
            if guild is None:
                await _safe_followup(interaction, "❌ Команда доступна только на сервере.", interaction_active=interaction_active)
                return

            settings = service.get_guild_settings(guild.id)
            if settings is None:
                await _safe_followup(
                    interaction,
                    "ℹ️ Настройки DiscordAuth ещё не заданы. Используй `/discordauth settings set`.",
                    interaction_active=interaction_active,
                )
                return

            await _safe_followup(
                interaction,
                "Текущие настройки DiscordAuth:\n" + _format_settings_summary(guild, settings),
                interaction_active=interaction_active,
            )

        @settings_group.command(name="validate", description="Проверить настройки DiscordAuth")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def validate_settings(interaction: discord.Interaction) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=False)

            guild = interaction.guild
            if guild is None:
                await _safe_followup(interaction, "❌ Команда доступна только на сервере.", interaction_active=interaction_active)
                return

            settings = service.get_guild_settings(guild.id)
            if settings is None:
                await _safe_followup(
                    interaction,
                    "ℹ️ Настройки DiscordAuth ещё не заданы. Используй `/discordauth settings set`.",
                    interaction_active=interaction_active,
                )
                return

            issues = await service.validate_guild_settings(guild, settings, bot_member=_resolve_bot_member(bot, guild))
            await _safe_followup(
                interaction,
                f"{_format_settings_summary(guild, settings)}\n\n{_format_validation_issues(issues)}",
                interaction_active=interaction_active,
            )

        discordauth_group.add_command(settings_group)
        bot.tree.add_command(discordauth_group)
        bot.add_listener(on_private_message, "on_message")

    async def on_ready(bot: commands.Bot) -> None:
        await runtime.on_ready(bot)
        bridge.start(bot=bot)

    def persistent_views():
        return [DiscordAuthPanelView(service)]

    return BotModule(
        name="discordauth",
        description="DiscordAuth bridge, настройка и стартовая панель привязки.",
        register=register,
        on_ready=on_ready,
        persistent_views=persistent_views,
    )
