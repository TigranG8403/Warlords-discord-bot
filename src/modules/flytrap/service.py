from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import discord
from discord.ext import commands

from .content import build_warning_embed
from .models import FlytrapAction, FlytrapConfig
from .repository import FlytrapRepository


logger = logging.getLogger(__name__)

AUDIT_REASON = "Warlords Flytrap: сообщение в канале-ловушке"
RECOVERY_MESSAGE_LIMIT = 100


class FlytrapService:
    def __init__(
        self,
        repository: FlytrapRepository,
        *,
        timeout_duration: timedelta = timedelta(hours=1),
    ) -> None:
        self.repository = repository
        self.timeout_duration = timeout_duration

    async def handle_message(self, message: discord.Message) -> None:
        guild = message.guild
        if guild is None or message.author.bot:
            return

        config = self.repository.get_config_by_channel(message.channel.id)
        if config is None or config.guild_id != guild.id:
            return

        if not self.repository.claim_incident(
            message_id=message.id,
            guild_id=guild.id,
            channel_id=message.channel.id,
            user_id=message.author.id,
            action=config.action,
        ):
            return

        target = message.author
        member = target if isinstance(target, discord.Member) else guild.get_member(target.id)
        if self._is_protected_user(guild, target, member):
            await self._safe_delete(message)
            await self._send_log(
                guild=guild,
                config=config,
                user=target,
                message=message,
                title="⚠️ Мухоловка: защищённый участник",
                description=(
                    "Сообщение удалено, но наказание не применено: владелец сервера "
                    "и администраторы защищены от автоматических действий."
                ),
                color=0xD49A35,
            )
            self.repository.finish_incident(message.id, status="protected")
            return

        if config.action is FlytrapAction.TIMEOUT and member is None:
            try:
                member = await guild.fetch_member(target.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                await self._safe_delete(message)
                await self._send_log(
                    guild=guild,
                    config=config,
                    user=target,
                    message=message,
                    title="❌ Ошибка Мухоловки",
                    description="Не удалось выдать тайм-аут: участник уже покинул сервер.",
                    color=0xA62929,
                )
                self.repository.finish_incident(
                    message.id,
                    status="failed",
                    detail="Участник не найден для выдачи тайм-аута.",
                )
                return

        try:
            await self._apply_action(guild, target, member, config.action)
            if config.action is FlytrapAction.TIMEOUT:
                await self._safe_delete(message)
        except (discord.Forbidden, discord.HTTPException) as error:
            await self._safe_delete(message)
            logger.warning(
                "Не удалось применить действие мухоловки %s к пользователю %s: %s",
                config.action.value,
                target.id,
                error,
            )
            await self._send_log(
                guild=guild,
                config=config,
                user=target,
                message=message,
                title="❌ Ошибка Мухоловки",
                description=(
                    f"Не удалось применить действие «{config.action.display_name}». "
                    "Проверьте права и положение роли бота."
                ),
                color=0xA62929,
            )
            self.repository.finish_incident(
                message.id,
                status="failed",
                detail=f"{type(error).__name__}: {error}",
            )
            return

        moderated_count = self.repository.finish_handled_incident(
            message_id=message.id,
            guild_id=guild.id,
        )
        await self._send_log(
            guild=guild,
            config=config,
            user=target,
            message=message,
            title="🪰 Мухоловка сработала",
            description=f"Применено действие: **{config.action.display_name}**.",
            color=0x6D1A1A,
        )
        await self._update_warning_message(
            channel=message.channel,
            config=config,
            moderated_count=moderated_count,
        )

    async def recover_recent_messages(self, bot: commands.Bot) -> None:
        removed_incidents = self.repository.purge_old_incidents()
        if removed_incidents:
            logger.info("Мухоловка удалила %s устаревших записей инцидентов.", removed_incidents)

        for config in self.repository.list_configs():
            channel = bot.get_channel(config.channel_id)
            if not isinstance(channel, discord.TextChannel):
                logger.warning(
                    "Канал Мухоловки %s для сервера %s не найден.",
                    config.channel_id,
                    config.guild_id,
                )
                continue

            await self._update_warning_message(
                channel=channel,
                config=config,
                moderated_count=config.moderated_count,
            )

            try:
                messages = [
                    message
                    async for message in channel.history(
                        limit=RECOVERY_MESSAGE_LIMIT,
                        after=discord.Object(id=config.warning_message_id),
                        oldest_first=False,
                    )
                ]
            except (discord.Forbidden, discord.HTTPException) as error:
                logger.warning(
                    "Не удалось проверить историю Мухоловки в канале %s: %s",
                    channel.id,
                    error,
                )
                continue

            for message in reversed(messages):
                await self.handle_message(message)

    @staticmethod
    async def _update_warning_message(
        *,
        channel: discord.abc.Messageable,
        config: FlytrapConfig,
        moderated_count: int,
    ) -> None:
        if not hasattr(channel, "fetch_message"):
            return

        try:
            warning = await channel.fetch_message(config.warning_message_id)
            await warning.edit(embed=build_warning_embed(moderated_count))
        except discord.NotFound:
            logger.warning(
                "Предупреждение Мухоловки %s в канале %s не найдено.",
                config.warning_message_id,
                config.channel_id,
            )
        except (discord.Forbidden, discord.HTTPException) as error:
            logger.warning(
                "Не удалось обновить счётчик Мухоловки в канале %s: %s",
                config.channel_id,
                error,
            )

    async def _apply_action(
        self,
        guild: discord.Guild,
        target: discord.abc.Snowflake,
        member: discord.Member | None,
        action: FlytrapAction,
    ) -> None:
        if action is FlytrapAction.TIMEOUT:
            if member is None:
                raise RuntimeError("Для тайм-аута требуется участник сервера.")
            await member.timeout(
                datetime.now(UTC) + self.timeout_duration,
                reason=AUDIT_REASON,
            )
            return

        await guild.ban(
            target,
            reason=AUDIT_REASON,
            delete_message_seconds=3600,
        )
        if action is FlytrapAction.SOFTBAN:
            await guild.unban(target, reason="Warlords Flytrap: softban завершён")

    @staticmethod
    def _is_protected_user(
        guild: discord.Guild,
        user: discord.abc.User,
        member: discord.Member | None,
    ) -> bool:
        return user.id == guild.owner_id or (
            member is not None and member.guild_permissions.administrator
        )

    @staticmethod
    async def _safe_delete(message: discord.Message) -> None:
        try:
            await message.delete()
        except discord.NotFound:
            pass
        except (discord.Forbidden, discord.HTTPException) as error:
            logger.warning("Не удалось удалить сообщение Мухоловки %s: %s", message.id, error)

    @staticmethod
    async def _send_log(
        *,
        guild: discord.Guild,
        config: FlytrapConfig,
        user: discord.abc.User,
        message: discord.Message,
        title: str,
        description: str,
        color: int,
    ) -> None:
        channel = guild.get_channel(config.log_channel_id)
        if channel is None or not hasattr(channel, "send"):
            logger.warning(
                "Канал журнала Мухоловки %s для сервера %s не найден.",
                config.log_channel_id,
                guild.id,
            )
            return

        content = message.content.strip() or "[сообщение без текста]"
        attachment_names = ", ".join(attachment.filename for attachment in message.attachments)
        if attachment_names:
            content = f"{content}\nВложения: {attachment_names}"

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=message.created_at,
        )
        embed.add_field(
            name="Участник",
            value=f"{user.mention} (`{user.id}`)",
            inline=False,
        )
        embed.add_field(
            name="Сообщение",
            value=discord.utils.escape_markdown(content)[:1000],
            inline=False,
        )
        embed.set_footer(text=f"Сообщение: {message.id}")

        try:
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (discord.Forbidden, discord.HTTPException) as error:
            logger.warning(
                "Не удалось записать инцидент Мухоловки в канал %s: %s",
                config.log_channel_id,
                error,
            )
