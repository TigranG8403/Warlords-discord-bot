from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from core.discord_interactions import safe_defer, safe_followup_send
from core.module import BotModule

from .models import FlytrapAction, FlytrapConfig
from .repository import FlytrapRepository
from .service import FlytrapService


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_PATH = PROJECT_ROOT / "data" / "flytrap.sqlite3"
EMBED_COLOR = 0x6D1A1A

ACTION_CHOICES = [
    app_commands.Choice(
        name="Softban: удалить недавний спам и разрешить вернуться",
        value=FlytrapAction.SOFTBAN.value,
    ),
    app_commands.Choice(
        name="Тайм-аут на один час",
        value=FlytrapAction.TIMEOUT.value,
    ),
    app_commands.Choice(
        name="Постоянный бан",
        value=FlytrapAction.BAN.value,
    ),
]


def _build_warning_embed(action: FlytrapAction) -> discord.Embed:
    embed = discord.Embed(
        title="🪰 Мухоловка",
        description=(
            "Этот канал является автоматической ловушкой для спам-ботов.\n\n"
            "**Не отправляйте сюда сообщения.** Любое сообщение будет удалено, "
            "а к его автору автоматически применится настроенное действие."
        ),
        color=EMBED_COLOR,
    )
    embed.set_footer(text=f"Действие: {action.display_name}")
    return embed


def _missing_permissions(
    *,
    trap_channel: discord.TextChannel,
    log_channel: discord.TextChannel,
    bot_member: discord.Member,
    action: FlytrapAction,
) -> list[str]:
    missing: list[str] = []
    trap_permissions = trap_channel.permissions_for(bot_member)
    log_permissions = log_channel.permissions_for(bot_member)

    required_trap_permissions = {
        "view_channel": "View Channel",
        "send_messages": "Send Messages",
        "read_message_history": "Read Message History",
        "manage_messages": "Manage Messages",
    }
    for attribute, label in required_trap_permissions.items():
        if not getattr(trap_permissions, attribute):
            missing.append(f"`{label}` в канале-ловушке")

    if not log_permissions.view_channel:
        missing.append("`View Channel` в канале журнала")
    if not log_permissions.send_messages:
        missing.append("`Send Messages` в канале журнала")
    if not log_permissions.embed_links:
        missing.append("`Embed Links` в канале журнала")

    if action is FlytrapAction.TIMEOUT and not bot_member.guild_permissions.moderate_members:
        missing.append("`Timeout Members` на сервере")
    if action in (FlytrapAction.SOFTBAN, FlytrapAction.BAN) and not bot_member.guild_permissions.ban_members:
        missing.append("`Ban Members` на сервере")

    return missing


async def _delete_warning(guild: discord.Guild, config: FlytrapConfig | None) -> None:
    if config is None:
        return

    channel = guild.get_channel(config.channel_id)
    if not isinstance(channel, discord.TextChannel):
        return

    try:
        message = await channel.fetch_message(config.warning_message_id)
        await message.delete()
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


def build_module() -> BotModule:
    repository = FlytrapRepository(DATABASE_PATH)
    service = FlytrapService(repository)

    def register(bot: commands.Bot) -> None:
        flytrap_group = app_commands.Group(
            name="flytrap",
            description="Управление защитным модулем «Мухоловка»",
        )

        @flytrap_group.command(
            name="setup",
            description="Настроить канал-ловушку для спам-ботов",
        )
        @app_commands.describe(
            channel="Канал-ловушка. Любое сообщение обычного участника вызовет наказание.",
            log_channel="Закрытый канал, в который будут отправляться отчёты.",
            action="Действие при срабатывании Мухоловки.",
        )
        @app_commands.choices(action=ACTION_CHOICES)
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def setup_flytrap(
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            log_channel: discord.TextChannel,
            action: app_commands.Choice[str],
        ) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=True)
            guild = interaction.guild
            if not interaction_active or guild is None:
                return

            if channel.id == log_channel.id:
                await safe_followup_send(
                    interaction,
                    "❌ Канал журнала должен отличаться от канала-ловушки.",
                    ephemeral=True,
                )
                return

            selected_action = FlytrapAction(action.value)
            bot_member = guild.me
            if bot_member is None:
                await safe_followup_send(
                    interaction,
                    "❌ Не удалось определить роль бота на сервере.",
                    ephemeral=True,
                )
                return

            missing_permissions = _missing_permissions(
                trap_channel=channel,
                log_channel=log_channel,
                bot_member=bot_member,
                action=selected_action,
            )
            if missing_permissions:
                await safe_followup_send(
                    interaction,
                    "❌ Мухоловке не хватает прав:\n- " + "\n- ".join(missing_permissions),
                    ephemeral=True,
                )
                return

            try:
                warning = await channel.send(
                    embed=_build_warning_embed(selected_action),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                try:
                    await warning.pin(reason="Панель защитного модуля «Мухоловка»")
                except (discord.Forbidden, discord.HTTPException):
                    logger.warning("Не удалось закрепить панель Мухоловки в канале %s.", channel.id)
            except (discord.Forbidden, discord.HTTPException):
                await safe_followup_send(
                    interaction,
                    "❌ Не удалось отправить предупреждение в канал-ловушку.",
                    ephemeral=True,
                )
                return

            previous_config = repository.get_config(guild.id)
            config = FlytrapConfig(
                guild_id=guild.id,
                channel_id=channel.id,
                log_channel_id=log_channel.id,
                action=selected_action,
                warning_message_id=warning.id,
            )
            repository.set_config(config)
            await _delete_warning(guild, previous_config)

            await safe_followup_send(
                interaction,
                (
                    f"✅ Мухоловка включена в {channel.mention}.\n"
                    f"Действие: **{selected_action.display_name}**.\n"
                    f"Журнал: {log_channel.mention}."
                ),
                ephemeral=True,
            )

        @flytrap_group.command(
            name="status",
            description="Показать текущую конфигурацию Мухоловки",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def flytrap_status(interaction: discord.Interaction) -> None:
            guild = interaction.guild
            config = repository.get_config(guild.id) if guild is not None else None
            if config is None:
                await interaction.response.send_message(
                    "ℹ️ Мухоловка на этом сервере не настроена.",
                    ephemeral=True,
                )
                return

            channel = guild.get_channel(config.channel_id)
            log_channel = guild.get_channel(config.log_channel_id)
            channel_label = channel.mention if channel is not None else f"`{config.channel_id}` (не найден)"
            log_label = (
                log_channel.mention
                if log_channel is not None
                else f"`{config.log_channel_id}` (не найден)"
            )
            await interaction.response.send_message(
                (
                    "## 🪰 Мухоловка включена\n"
                    f"Канал: {channel_label}\n"
                    f"Журнал: {log_label}\n"
                    f"Действие: **{config.action.display_name}**"
                ),
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )

        @flytrap_group.command(
            name="disable",
            description="Отключить Мухоловку",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def disable_flytrap(interaction: discord.Interaction) -> None:
            interaction_active = await safe_defer(interaction, ephemeral=True, thinking=True)
            guild = interaction.guild
            if not interaction_active or guild is None:
                return

            config = repository.get_config(guild.id)
            if config is None:
                await safe_followup_send(
                    interaction,
                    "ℹ️ Мухоловка уже отключена.",
                    ephemeral=True,
                )
                return

            repository.delete_config(guild.id)
            await _delete_warning(guild, config)
            await safe_followup_send(
                interaction,
                "✅ Мухоловка отключена. Сам канал не удалялся.",
                ephemeral=True,
            )

        async def on_message(message: discord.Message) -> None:
            await service.handle_message(message)

        bot.tree.add_command(flytrap_group)
        bot.add_listener(on_message, "on_message")

    async def on_ready(bot: commands.Bot) -> None:
        await service.recover_recent_messages(bot)

    return BotModule(
        name="flytrap",
        description="Канал-ловушка для автоматического удаления спам-ботов.",
        register=register,
        on_ready=on_ready,
    )

