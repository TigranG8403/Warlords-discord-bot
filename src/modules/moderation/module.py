from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from core.discord_interactions import safe_response_send_message
from core.module import BotModule

from .ai_client import ModerationAiClient
from .backfill import backfill_user_observations
from .config import ModerationEvaluationInput, ModerationRuntimeConfig
from .engagement import (
    is_bot_mentioned,
    is_bot_role_mentioned,
    is_low_signal_persona_message,
    is_protected_member,
    is_reply_to_bot,
    is_textually_addressed_to_bot,
    remember_channel_reply,
    remember_persona_context,
    should_continue_persona_dialogue,
    should_skip_recent_channel_duplicate_reply,
    should_skip_duplicate_persona_reply,
    should_suppress_persona_text_reply,
)
from .knowledge import (
    DEFAULT_SERVER_FACTS,
    DEFAULT_SERVER_RULES,
    EXTRA_KNOWN_PROFILES,
    EXTRA_SERVER_FACTS,
    SEEDED_KNOWN_PROFILES,
    SOFT_ESCALATION_FACTS,
)
from .memory import PersonaMemoryStore
from .ocr import AttachmentOcrService
from .repository import ModerationRepository
from .service import ModerationService


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODERATION_DB_PATH = PROJECT_ROOT / "data" / "moderation.sqlite3"


def _build_runtime_config() -> ModerationRuntimeConfig:
    return ModerationRuntimeConfig(
        candidate_window=int(os.getenv("MODERATION_CONTEXT_WINDOW", "10")),
        ai_url=os.getenv("MODERATION_AI_URL", "").strip(),
        ai_token=os.getenv("MODERATION_AI_TOKEN", "").strip(),
        ai_timeout_seconds=int(os.getenv("MODERATION_AI_TIMEOUT", "60")),
        confidence_threshold=float(os.getenv("MODERATION_CONFIDENCE_THRESHOLD", "0.78")),
        max_reply_length=int(os.getenv("MODERATION_REPLY_MAX_LENGTH", "220")),
        server_rules=DEFAULT_SERVER_RULES,
        server_facts=DEFAULT_SERVER_FACTS + EXTRA_SERVER_FACTS + SOFT_ESCALATION_FACTS,
    )


def build_module() -> BotModule:
    repository = ModerationRepository(MODERATION_DB_PATH)
    repository.seed_known_profiles(SEEDED_KNOWN_PROFILES + EXTRA_KNOWN_PROFILES)

    runtime_config = _build_runtime_config()
    character_refresh_inflight: set[tuple[int, int]] = set()
    memory_store = PersonaMemoryStore(ttl_seconds=int(os.getenv("MODERATION_PERSONA_MEMORY_TTL", "300")))
    ocr_service = AttachmentOcrService(
        languages=os.getenv("MODERATION_OCR_LANGUAGES", "rus+eng"),
        max_images=int(os.getenv("MODERATION_OCR_MAX_IMAGES", "8")),
        timeout_seconds=int(os.getenv("MODERATION_OCR_TIMEOUT", "20")),
    )
    ai_client = ModerationAiClient(
        provider=os.getenv("MODERATION_AI_PROVIDER", "").strip(),
        base_url=os.getenv("MODERATION_AI_BASE_URL", "").strip() or runtime_config.ai_url,
        shared_token=runtime_config.ai_token,
        api_key=os.getenv("MODERATION_AI_API_KEY", "").strip(),
        model=os.getenv("MODERATION_AI_MODEL", "").strip(),
        timeout_seconds=runtime_config.ai_timeout_seconds,
    )
    service = ModerationService(
        repository,
        ai_client=ai_client if ai_client.is_configured() else None,
        ocr_service=ocr_service if ocr_service.is_available() else None,
        runtime_config=runtime_config,
    )

    def register(bot: commands.Bot) -> None:
        moderation_group = app_commands.Group(name="moderation", description="Настройки автомодерации и профилей игроков")

        @moderation_group.command(name="setup", description="Настроить архив и пинг модерации")
        @app_commands.describe(
            archive_channel="Канал для архива и доказательств автомодерации.",
            admin_role="Роль, которую нужно пинговать при рекламе и сомнительных ссылках.",
            admin_user="Пользователь, которого нужно пинговать при рекламе и сомнительных ссылках.",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def setup(
            interaction: discord.Interaction,
            archive_channel: discord.TextChannel,
            admin_role: discord.Role | None = None,
            admin_user: discord.Member | None = None,
        ) -> None:
            if interaction.guild is None:
                await safe_response_send_message(
                    interaction,
                    "Эту команду можно использовать только на сервере.",
                    ephemeral=True,
                )
                return

            repository.save_guild_settings(
                interaction.guild.id,
                archive_channel_id=archive_channel.id,
                admin_alert_role_id=admin_role.id if admin_role is not None else None,
                admin_alert_user_id=admin_user.id if admin_user is not None else None,
            )
            await safe_response_send_message(
                interaction,
                service.format_status_message(repository.get_guild_settings(interaction.guild.id)),
                ephemeral=True,
            )

        @moderation_group.command(name="status", description="Показать текущий статус автомодерации")
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def status(interaction: discord.Interaction) -> None:
            settings = repository.get_guild_settings(interaction.guild.id) if interaction.guild else None
            await safe_response_send_message(interaction, service.format_status_message(settings), ephemeral=True)

        @moderation_group.command(name="backfill_profiles", description="Единоразово собрать историю сервера в базу профилей")
        @app_commands.describe(
            reset_existing="Очистить текущие наблюдения перед полным сканом истории.",
            refresh_summaries="После скана сразу пересобрать AI-сводки по игрокам.",
        )
        @app_commands.default_permissions(administrator=True)
        @app_commands.checks.has_permissions(administrator=True)
        async def backfill_profiles(
            interaction: discord.Interaction,
            reset_existing: bool = True,
            refresh_summaries: bool = True,
        ) -> None:
            if interaction.guild is None:
                await safe_response_send_message(
                    interaction,
                    "Эту команду можно использовать только на сервере.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True, thinking=True)
            settings = repository.get_guild_settings(interaction.guild.id)
            stats = await backfill_user_observations(
                repository=repository,
                ai_client=service.ai_client,
                guild=interaction.guild,
                archive_channel_id=settings.archive_channel_id if settings else None,
                bot_user_id=bot.user.id if bot.user else None,
                reset_existing=reset_existing,
                refresh_summaries=refresh_summaries,
            )
            await interaction.followup.send(
                (
                    "Backfill профилей завершён.\n"
                    f"Каналов просмотрено: {stats['channels']}\n"
                    f"Сообщений учтено: {stats['messages']}\n"
                    f"Игроков в базе после скана: {stats['users']}\n"
                    f"AI-сводок обновлено: {stats['summaries']}"
                ),
                ephemeral=True,
            )

        async def on_message(message: discord.Message) -> None:
            if message.guild is None or message.author.bot or message.webhook_id is not None:
                return
            if not isinstance(message.author, discord.Member):
                return

            settings = repository.get_guild_settings(message.guild.id)
            if settings is None or message.channel.id == settings.archive_channel_id:
                return

            bot_user_id = bot.user.id if bot.user else None
            reply_to_bot = await _detect_reply_to_bot(message, bot_user_id)
            bot_mentioned = is_bot_mentioned(message, bot_user_id)
            bot_role_mentioned = is_bot_role_mentioned(
                message,
                bot_user=bot.user,
                bot_member=message.guild.me,
            )
            protected_member = is_protected_member(message.author, message.guild, bot_user_id)
            memory_entry = memory_store.get(
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                user_id=message.author.id,
            )
            addressed_to_bot = (
                reply_to_bot
                or bot_mentioned
                or bot_role_mentioned
                or is_textually_addressed_to_bot(
                    message,
                    bot_user=bot.user,
                    bot_member=message.guild.me,
                )
                or should_continue_persona_dialogue(
                    message=message,
                    memory_entry=memory_entry,
                )
            )

            if not service.should_consider(message, addressed_to_bot=addressed_to_bot):
                if addressed_to_bot:
                    await _send_persona_reply(
                        service=service,
                        memory_store=memory_store,
                        message=message,
                        reply_to_bot=reply_to_bot,
                        bot_mentioned=bot_mentioned,
                        previous_user_content=memory_entry.last_user_content if memory_entry else "",
                        previous_bot_reply=memory_entry.last_bot_reply if memory_entry else "",
                        previous_bot_replies=memory_entry.recent_bot_replies if memory_entry else (),
                        previous_remembered_at=memory_entry.remembered_at if memory_entry else 0,
                        author_is_protected=protected_member,
                    )
                return

            payload = await service.build_payload(
                message,
                reply_to_bot=reply_to_bot,
                bot_mentioned=bot_mentioned,
                addressed_to_bot=addressed_to_bot,
                author_is_protected=protected_member,
            )
            decision = service.evaluate(payload)

            _record_observation(repository, payload=payload, decision=decision, addressed_to_bot=addressed_to_bot)
            _schedule_user_character_refresh(
                repository=repository,
                ai_client=service.ai_client,
                payload=payload,
                inflight=character_refresh_inflight,
            )

            if decision.decision == "allow":
                if addressed_to_bot:
                    await _send_persona_reply(
                        service=service,
                        memory_store=memory_store,
                        message=message,
                        reply_to_bot=reply_to_bot,
                        bot_mentioned=bot_mentioned,
                        previous_user_content=memory_entry.last_user_content if memory_entry else "",
                        previous_bot_reply=memory_entry.last_bot_reply if memory_entry else "",
                        previous_bot_replies=memory_entry.recent_bot_replies if memory_entry else (),
                        previous_remembered_at=memory_entry.remembered_at if memory_entry else 0,
                        author_is_protected=protected_member,
                    )
                return

            if protected_member and decision.decision in {"light_violation", "ban_violation"}:
                decision = service.build_protected_reply_decision(
                    author_id=message.author.id,
                    display_name=getattr(message.author, "display_name", message.author.name),
                    decision=decision,
                )

            try:
                await service.archive_decision(settings=settings, message=message, payload=payload, decision=decision)
            except discord.HTTPException as error:
                logger.warning("Не удалось записать moderation-событие по сообщению %s: %s", message.id, error)

            await _apply_decision(
                service=service,
                memory_store=memory_store,
                settings=settings,
                message=message,
                decision=decision,
                addressed_to_bot=addressed_to_bot,
                reply_to_bot=reply_to_bot,
                bot_mentioned=bot_mentioned,
                previous_user_content=memory_entry.last_user_content if memory_entry else "",
                previous_bot_reply=memory_entry.last_bot_reply if memory_entry else "",
                previous_bot_replies=memory_entry.recent_bot_replies if memory_entry else (),
                previous_remembered_at=memory_entry.remembered_at if memory_entry else 0,
                author_is_protected=protected_member,
            )

        bot.tree.add_command(moderation_group)
        bot.add_listener(on_message, "on_message")

    return BotModule(
        name="moderation",
        description="Контекстная автомодерация чата с архивом, OCR и AI-классификацией.",
        register=register,
    )


def _record_observation(
    repository: ModerationRepository,
    *,
    payload: ModerationEvaluationInput,
    decision,
    addressed_to_bot: bool,
) -> None:
    repository.record_user_observation(
        guild_id=payload.guild_id,
        user_id=payload.author_id,
        author_name=payload.author_display_name,
        role_names=payload.author_role_names,
        content=payload.content,
        decision=decision.decision,
        addressed_to_bot=addressed_to_bot,
        labels=decision.labels,
    )


async def _detect_reply_to_bot(message: discord.Message, bot_user_id: int | None) -> bool:
    if is_reply_to_bot(message, bot_user_id):
        return True
    if bot_user_id is None or message.reference is None or message.reference.message_id is None:
        return False

    for candidate in (getattr(message.reference, "resolved", None), getattr(message.reference, "cached_message", None)):
        if getattr(getattr(candidate, "author", None), "id", None) == bot_user_id:
            return True

    target_channel = None
    channel_id = getattr(message.reference, "channel_id", None)
    guild = getattr(message, "guild", None)
    if guild is not None and channel_id is not None:
        target_channel = guild.get_channel_or_thread(channel_id)
        if target_channel is None:
            try:
                target_channel = await guild.fetch_channel(channel_id)
            except discord.HTTPException:
                target_channel = None

    if target_channel is None:
        target_channel = message.channel

    if not hasattr(target_channel, "fetch_message"):
        return False

    try:
        referenced_message = await target_channel.fetch_message(message.reference.message_id)
    except discord.HTTPException:
        return False
    return referenced_message.author.id == bot_user_id


async def _apply_decision(
    *,
    service: ModerationService,
    memory_store: PersonaMemoryStore,
    settings,
    message: discord.Message,
    decision,
    addressed_to_bot: bool,
    reply_to_bot: bool,
    bot_mentioned: bool,
    previous_user_content: str,
    previous_bot_reply: str,
    previous_bot_replies: tuple[str, ...],
    previous_remembered_at: int,
    author_is_protected: bool,
) -> None:
    if decision.decision == "review":
        if decision.reply_text or decision.reaction_emoji:
            await _send_decision_response(
                service=service,
                memory_store=memory_store,
                message=message,
                decision=decision,
                addressed_to_bot=addressed_to_bot,
            )
        elif addressed_to_bot:
            await _send_persona_reply(
                service=service,
                memory_store=memory_store,
                message=message,
                reply_to_bot=reply_to_bot,
                bot_mentioned=bot_mentioned,
                previous_user_content=previous_user_content,
                previous_bot_reply=previous_bot_reply,
                previous_bot_replies=previous_bot_replies,
                previous_remembered_at=previous_remembered_at,
                author_is_protected=author_is_protected,
            )
        return

    if decision.decision == "scam_alert":
        await _send_decision_response(
            service=service,
            memory_store=memory_store,
            message=message,
            decision=decision,
            addressed_to_bot=addressed_to_bot,
        )
        await service.send_admin_alert(settings=settings, message=message, decision=decision)
        return

    await _send_decision_response(
        service=service,
        memory_store=memory_store,
        message=message,
        decision=decision,
        addressed_to_bot=addressed_to_bot,
    )

    if decision.should_delete_message:
        await service.delete_message(message)

    if decision.decision == "ban_violation":
        await service.apply_member_ban(message.author, reason=decision.reason)
        return

    if decision.should_timeout_user and decision.timeout_minutes > 0:
        await service.apply_member_timeout(
            message.author,
            timeout_minutes=decision.timeout_minutes,
            reason=decision.reason,
        )


async def _send_decision_response(
    *,
    service: ModerationService,
    memory_store: PersonaMemoryStore,
    message: discord.Message,
    decision,
    addressed_to_bot: bool,
) -> None:
    if decision.reply_text:
        await service.send_public_reply(message, decision=decision)
        remember_channel_reply(memory_store, message=message, bot_reply=decision.reply_text)
        if addressed_to_bot:
            remember_persona_context(memory_store, message=message, bot_reply=decision.reply_text)
    if decision.reaction_emoji:
        await service.send_reaction(message, decision.reaction_emoji)


async def _send_persona_reply(
    service: ModerationService,
    memory_store: PersonaMemoryStore,
    message: discord.Message,
    *,
    reply_to_bot: bool,
    bot_mentioned: bool,
    previous_user_content: str,
    previous_bot_reply: str,
    previous_bot_replies: tuple[str, ...],
    previous_remembered_at: int,
    author_is_protected: bool,
) -> None:
    if service.ai_client is None or not service.ai_client.supports_persona():
        return

    recent_channel_replies = (
        memory_store.recent_channel_replies(
            guild_id=message.guild.id,
            channel_id=message.channel.id,
        )
        if message.guild is not None
        else ()
    )
    payload = await service.build_payload(
        message,
        reply_to_bot=reply_to_bot,
        bot_mentioned=bot_mentioned,
        addressed_to_bot=True,
        author_is_protected=author_is_protected,
    )
    response = service.ai_client.generate_persona_response(
        payload=payload,
        previous_user_content=previous_user_content,
        previous_bot_reply=previous_bot_reply,
        recent_channel_replies=recent_channel_replies,
    )
    if response is None:
        return

    reply_text = response.reply_text
    reaction_emoji = response.reaction_emoji
    if not reply_text and not reaction_emoji:
        return

    normalized_reply = " ".join(reply_text.split()).strip()
    if should_suppress_persona_text_reply(message, normalized_reply):
        normalized_reply = ""
        reply_text = ""

    if should_skip_duplicate_persona_reply(
        current_user_content=message.content,
        previous_user_content=previous_user_content,
        previous_bot_reply=previous_bot_reply,
        recent_bot_replies=previous_bot_replies,
        candidate_reply=normalized_reply,
        reaction_emoji=reaction_emoji,
        previous_remembered_at=previous_remembered_at,
    ):
        return
    if should_skip_recent_channel_duplicate_reply(
        candidate_reply=normalized_reply,
        recent_channel_replies=recent_channel_replies,
        current_user_content=message.content,
    ):
        return

    if not normalized_reply and not reaction_emoji:
        return

    if reply_text:
        await service.send_reply_text(message, reply_text)
        remember_persona_context(memory_store, message=message, bot_reply=reply_text)
    if reaction_emoji:
        await service.send_reaction(message, reaction_emoji)


def _schedule_user_character_refresh(
    *,
    repository: ModerationRepository,
    ai_client: ModerationAiClient | None,
    payload: ModerationEvaluationInput,
    inflight: set[tuple[int, int]],
) -> None:
    if ai_client is None or not ai_client.supports_persona():
        return
    key = (payload.guild_id, payload.author_id)
    if key in inflight:
        return
    if not repository.should_refresh_user_character(guild_id=payload.guild_id, user_id=payload.author_id):
        return
    inflight.add(key)
    asyncio.create_task(
        _refresh_user_character_summary(
            repository=repository,
            ai_client=ai_client,
            payload=payload,
            inflight=inflight,
        )
    )


async def _refresh_user_character_summary(
    *,
    repository: ModerationRepository,
    ai_client: ModerationAiClient,
    payload: ModerationEvaluationInput,
    inflight: set[tuple[int, int]],
) -> None:
    key = (payload.guild_id, payload.author_id)
    try:
        summary = await asyncio.to_thread(
            ai_client.generate_user_character_summary,
            display_name=payload.author_display_name,
            role_names=payload.author_role_names,
            known_profile=payload.author_known_profile,
            recent_samples=repository.get_recent_user_samples(guild_id=payload.guild_id, user_id=payload.author_id),
            existing_summary=repository.describe_user_character(guild_id=payload.guild_id, user_id=payload.author_id),
        )
        if summary:
            repository.save_user_character_summary(
                guild_id=payload.guild_id,
                user_id=payload.author_id,
                summary=summary,
            )
    finally:
        inflight.discard(key)
