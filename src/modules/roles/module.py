from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from core.discord_interactions import safe_defer, safe_followup_send
from core.module import BotModule
from core.panel_runtime import PanelRenderResult, PanelRuntime
from core.time_of_day import period_key, pick_banner_asset_path
from modules.tickets.banner import make_banner_file
from modules.tickets.config import get_msk_time

from .repository import RolePanelRecord, RolePanelRepository

logger = logging.getLogger(__name__)

NEWS_EMOJI = "🔔"
GAMER_EMOJI = "🎮"
ROLES_BANNER_FILENAME = "roles_banner.png"
ROLES_BANNER_TEXT = "Roles"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSETS_DIR = PROJECT_ROOT / "assets"
PANEL_REGISTRY_DB_PATH = PROJECT_ROOT / "data" / "panel_registry.sqlite3"
ROLE_PANELS_LEGACY_PATH = PROJECT_ROOT / "data" / "role_panels.json"
ROLES_COLOR = 0x6D1A1A


def _build_roles_embed(*, news_role: discord.Role, gamer_role: discord.Role, image_url: str | None) -> discord.Embed:
    embed = discord.Embed(
        description=(
            "## 🎭 **Выбор ролей**\n\n"
            "Выберите интересующие вас роли, нажав на соответствующую реакцию.\n"
            "Чтобы **снять роль**, нажмите реакцию ещё раз.\n\n"
            f"{NEWS_EMOJI} {news_role.mention}  - получать уведомления о **глобальных событиях и новостях сервера**.\n\n"
            f"{GAMER_EMOJI} {gamer_role.mention}  - получать уведомления о **сборах поиграть в разные игры** и доступ к "
            "**специальному игровому чату**."
        ),
        color=ROLES_COLOR,
    )
    if image_url:
        embed.set_image(url=image_url)
    return embed


async def _safe_followup(interaction: discord.Interaction, message: str, *, interaction_active: bool) -> None:
    if not interaction_active:
        return

    await safe_followup_send(interaction, message, ephemeral=True)


async def _resolve_member(
    guild: discord.Guild,
    user_id: int,
    payload_member: discord.Member | None = None,
) -> discord.Member | None:
    if payload_member is not None:
        return payload_member

    member = guild.get_member(user_id)
    if member is not None:
        return member

    try:
        return await guild.fetch_member(user_id)
    except discord.NotFound:
        return None


async def _apply_role_change(
    *,
    bot: commands.Bot,
    repository: RolePanelRepository,
    payload: discord.RawReactionActionEvent,
    add_role: bool,
) -> None:
    if payload.guild_id is None or bot.user is None or payload.user_id == bot.user.id:
        return

    record = repository.get(payload.message_id)
    if record is None or record.guild_id != payload.guild_id:
        return

    role_id = None
    emoji = str(payload.emoji)
    if emoji == NEWS_EMOJI:
        role_id = record.news_role_id
    elif emoji == GAMER_EMOJI:
        role_id = record.gamer_role_id
    else:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    member = await _resolve_member(guild, payload.user_id, getattr(payload, "member", None))
    role = guild.get_role(role_id)
    if member is None or role is None or member.bot:
        return

    try:
        if add_role:
            await member.add_roles(role, reason="Reaction role opt-in")
        else:
            await member.remove_roles(role, reason="Reaction role opt-out")
    except discord.NotFound:
        repository.delete(payload.message_id)
    except discord.Forbidden:
        logger.warning(
            "Не удалось изменить роль %s для пользователя %s: не хватает прав.",
            role_id,
            payload.user_id,
        )


def build_module() -> BotModule:
    repository = RolePanelRepository(
        PANEL_REGISTRY_DB_PATH,
        legacy_path=ROLE_PANELS_LEGACY_PATH,
    )

    def render_panel(record: RolePanelRecord, channel: discord.TextChannel) -> PanelRenderResult | None:
        news_role = channel.guild.get_role(record.news_role_id)
        gamer_role = channel.guild.get_role(record.gamer_role_id)
        if news_role is None or gamer_role is None:
            return None

        banner_file = make_banner_file(
            asset_path=pick_banner_asset_path(
                assets_dir=ASSETS_DIR,
                stem="minecraft",
                current_time=get_msk_time(),
            ),
            text=ROLES_BANNER_TEXT,
            filename=ROLES_BANNER_FILENAME,
        )
        image_url = f"attachment://{ROLES_BANNER_FILENAME}" if banner_file is not None else None
        return PanelRenderResult(
            embed=_build_roles_embed(
                news_role=news_role,
                gamer_role=gamer_role,
                image_url=image_url,
            ),
            files=(banner_file,) if banner_file is not None else (),
            allowed_mentions=discord.AllowedMentions.none(),
        )

    runtime = PanelRuntime(
        name="roles",
        repository=repository,
        render_panel=render_panel,
        period_getter=lambda: period_key(get_msk_time()),
        logger=logger,
    )

    def register(bot: commands.Bot) -> None:
        runtime.bind(bot)

        roles_group = app_commands.Group(name="roles", description="Управление панелью выбора ролей")

        @roles_group.command(name="panel", description="Опубликовать панель выбора ролей")
        @app_commands.describe(
            news_role="Роль для уведомлений о новостях.",
            gamer_role="Роль для уведомлений об игровых сборах.",
            channel="Канал, в который нужно отправить панель. Если не указан, используется текущий.",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def publish_panel(
            interaction: discord.Interaction,
            news_role: discord.Role,
            gamer_role: discord.Role,
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

            record = RolePanelRecord(
                guild_id=target_channel.guild.id,
                channel_id=target_channel.id,
                news_role_id=news_role.id,
                gamer_role_id=gamer_role.id,
            )
            message = await runtime.publish(target_channel, record)

            try:
                await message.add_reaction(NEWS_EMOJI)
                await message.add_reaction(GAMER_EMOJI)
            except (discord.Forbidden, discord.HTTPException):
                repository.delete(message.id)
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass
                await _safe_followup(
                    interaction,
                    "❌ Не удалось добавить реакции. Проверь права `Add Reactions` и `Read Message History`.",
                    interaction_active=interaction_active,
                )
                return

            await _safe_followup(
                interaction,
                f"✅ Панель выбора ролей отправлена в {target_channel.mention}.",
                interaction_active=interaction_active,
            )

        async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
            await _apply_role_change(
                bot=bot,
                repository=repository,
                payload=payload,
                add_role=True,
            )

        async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent) -> None:
            await _apply_role_change(
                bot=bot,
                repository=repository,
                payload=payload,
                add_role=False,
            )

        bot.tree.add_command(roles_group)
        bot.add_listener(on_raw_reaction_add, "on_raw_reaction_add")
        bot.add_listener(on_raw_reaction_remove, "on_raw_reaction_remove")

    async def on_ready(bot: commands.Bot) -> None:
        await runtime.on_ready(bot)

    return BotModule(
        name="roles",
        description="Панель выбора ролей по реакциям.",
        register=register,
        on_ready=on_ready,
    )
