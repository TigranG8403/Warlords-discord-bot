from __future__ import annotations

import time

import discord
from discord.ext import commands

from core.discord_interactions import safe_followup_send, safe_send_ephemeral
from .config import DiscordAuthGuildSettings, DiscordAuthPlayerRecord
from .service import DiscordAuthService


def _resolve_bot_member(bot: commands.Bot, guild: discord.Guild) -> discord.Member | None:
    if bot.user is None:
        return None
    return guild.get_member(bot.user.id)


def _format_settings_summary(guild: discord.Guild, settings: DiscordAuthGuildSettings) -> str:
    verify_role = guild.get_role(settings.verify_role_id)
    admin_role = guild.get_role(settings.admin_command_role_id)

    verify_role_label = verify_role.mention if verify_role is not None else f"`{settings.verify_role_id}` (не найдена)"
    admin_role_label = admin_role.mention if admin_role is not None else f"`{settings.admin_command_role_id}` (не найдена)"
    return "\n".join(
        (
            f"guildId: `{settings.guild_id}`",
            f"verifyRoleId: {verify_role_label}",
            f"adminCommandRoleId: {admin_role_label}",
        )
    )


def _format_validation_issues(issues: list[str]) -> str:
    if not issues:
        return "✅ Проверка пройдена: настройки выглядят корректно."
    return "\n".join(["⚠️ Найдены проблемы:"] + [f"- {issue}" for issue in issues])


async def _safe_followup(interaction: discord.Interaction, message: str, *, interaction_active: bool) -> None:
    if interaction_active:
        sent = await safe_followup_send(interaction, message, ephemeral=True)
        if sent:
            return

    await safe_send_ephemeral(interaction, message)


def _resolve_link_response(service: DiscordAuthService, user: discord.abc.User, code: str) -> tuple[bool, str]:
    normalized_code = code.strip().upper()
    if not normalized_code:
        return False, "❌ Пришли код привязки в формате `link ABC123`."

    existing = service.find_player_by_discord_user_id(user.id)
    if existing is not None:
        return False, f"ℹ️ Этот Discord уже привязан к **{existing.player_name}**."

    player = service.consume_link_code(
        code=normalized_code,
        discord_user_id=user.id,
        discord_username=user.name,
        discord_display_name=user.display_name,
    )
    if player is None:
        return False, "❌ Код не найден или уже истёк. Зайди на сервер ещё раз и получи новый код."

    return True, f"✅ Аккаунт **{player.player_name}** привязан к Discord. Теперь можно снова заходить на сервер."


def _extract_link_code_from_message(content: str) -> str | None:
    normalized = content.strip()
    if not normalized:
        return None

    lowered = normalized.casefold()
    if lowered == "link":
        return ""

    prefix = "link "
    if lowered.startswith(prefix):
        return normalized[len(prefix):].strip()

    return None


def _describe_admin_role(guild: discord.Guild, role_id: int) -> str:
    role = guild.get_role(role_id)
    if role is not None:
        return role.mention
    return f"`{role_id}`"


async def _ensure_admin_command_access(
    service: DiscordAuthService,
    interaction: discord.Interaction,
    *,
    interaction_active: bool,
) -> tuple[discord.Guild, DiscordAuthGuildSettings, discord.Member] | None:
    guild = interaction.guild
    if guild is None:
        await _safe_followup(interaction, "❌ Команда доступна только на сервере.", interaction_active=interaction_active)
        return None

    settings = service.get_guild_settings(guild.id)
    if settings is None:
        await _safe_followup(
            interaction,
            "ℹ️ Настройки DiscordAuth ещё не заданы. Используй `/discordauth settings set`.",
            interaction_active=interaction_active,
        )
        return None

    member = interaction.user if isinstance(interaction.user, discord.Member) else guild.get_member(interaction.user.id)
    if member is None:
        await _safe_followup(
            interaction,
            "❌ Не удалось определить участника сервера для проверки прав.",
            interaction_active=interaction_active,
        )
        return None

    has_admin_role = any(role.id == settings.admin_command_role_id for role in member.roles)
    if not member.guild_permissions.administrator and not has_admin_role:
        await _safe_followup(
            interaction,
            f"❌ Для этой команды нужна роль {_describe_admin_role(guild, settings.admin_command_role_id)}.",
            interaction_active=interaction_active,
        )
        return None

    return guild, settings, member


def _format_player_target(record: DiscordAuthPlayerRecord) -> str:
    return f"**{record.player_name}** (`{record.player_uuid}`)"


def _resolve_player_query(service: DiscordAuthService, query: str) -> tuple[DiscordAuthPlayerRecord | None, str | None]:
    normalized = query.strip()
    if not normalized:
        return None, "❌ Укажи ник игрока или UUID."

    direct = service.get_player(normalized)
    if direct is not None:
        return direct, None

    lowered = normalized.casefold()
    players = service.list_players()

    for record in players:
        if record.player_name.casefold() == lowered:
            return record, None

    prefix_matches = [record for record in players if record.player_name.casefold().startswith(lowered)]
    if len(prefix_matches) == 1:
        return prefix_matches[0], None
    if len(prefix_matches) > 1:
        names = ", ".join(record.player_name for record in prefix_matches[:5])
        return None, f"❌ Найдено несколько игроков: {names}. Уточни ник или выбери UUID из автодополнения."

    contains_matches = [record for record in players if lowered in record.player_name.casefold()]
    if len(contains_matches) == 1:
        return contains_matches[0], None
    if len(contains_matches) > 1:
        names = ", ".join(record.player_name for record in contains_matches[:5])
        return None, f"❌ Найдено несколько игроков: {names}. Уточни ник или выбери UUID из автодополнения."

    return None, "❌ Игрок не найден в базе DiscordAuth."


def _build_player_choice_name(record: DiscordAuthPlayerRecord) -> str:
    parts: list[str] = []
    if record.is_online:
        parts.append("онлайн")
    if record.access_state.strip().upper() == "BLOCKED":
        parts.append("пермабан")
    elif record.temp_ban_until > int(time.time()):
        parts.append("темпбан")
    suffix = f" ({', '.join(parts)})" if parts else ""
    return f"{record.player_name}{suffix}"[:100]


def _build_dm_instruction_embed(bot_user: discord.ClientUser | None) -> discord.Embed:
    embed = discord.Embed(
        title="Привязка Minecraft-аккаунта",
        description=(
            "Подробная инструкция:\n\n"
            "1. Зайди на Minecraft-сервер и получи код из сообщения при входе.\n"
            "2. Отправь код сюда в ЛС.\n"
            "3. После успешной привязки снова зайди на сервер.\n"
            "4. Если бот запросит подтверждение входа, просто нажми кнопку в этом же диалоге."
        ),
        color=0xF2C27B,
    )
    embed.add_field(
        name="Как отправить код",
        value="`link ABC123`",
        inline=False,
    )
    embed.add_field(
        name="Если код не подошёл",
        value="Зайди на сервер ещё раз и получи новый код.",
        inline=False,
    )
    return embed


class DiscordAuthPanelView(discord.ui.View):
    def __init__(self, service: DiscordAuthService) -> None:
        super().__init__(timeout=None)
        self.service = service

    @discord.ui.button(
        label="Получить инструкцию в ЛС",
        style=discord.ButtonStyle.primary,
        emoji="✉",
        custom_id="discordauth:dm_help",
    )
    async def send_dm_help(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        try:
            channel = await interaction.user.create_dm()
            await channel.send(embed=_build_dm_instruction_embed(interaction.client.user))
        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Не удалось отправить сообщение в ЛС. Проверь, открыты ли личные сообщения от участников сервера.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "✅ Подробную инструкцию отправил в ЛС. Если код уже есть, просто ответь туда: `link ABC123`.",
            ephemeral=True,
        )


def _build_panel_embed(*, image_url: str | None) -> discord.Embed:
    embed = discord.Embed(
        title="Привязка аккаунта",
        description=(
            "Коротко, как это работает:\n\n"
            "1. Зайди на Minecraft-сервер и получи код привязки.\n"
            "2. Нажми кнопку ниже, чтобы получить инструкцию в ЛС.\n"
            "3. Отправь код боту в личные сообщения.\n"
            "4. После привязки зайди на сервер ещё раз."
        ),
        color=0xF2C27B,
    )
    if image_url is not None:
        embed.set_image(url=image_url)
    return embed
