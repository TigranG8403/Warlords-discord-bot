from __future__ import annotations

import asyncio
import logging
import re
from datetime import timedelta

import discord

from .ai_client import ModerationAiClient
from .archive import (
    build_archive_embed,
    build_archive_search_text,
    build_compact_archive_search_text,
    enrich_reply_mentions,
)
from .config import (
    ModerationContextMessage,
    ModerationDecision,
    ModerationEvaluationInput,
    ModerationEventRecord,
    ModerationGuildSettings,
    ModerationHistorySnapshot,
    ModerationRuntimeConfig,
)
from .ocr import AttachmentOcrService, looks_like_meta_moderation_ocr
from .policy import build_protected_review, choose_moderation_decision
from .repository import ModerationRepository
from .rules import evaluate_with_rules, should_consider_message_for_moderation


logger = logging.getLogger(__name__)


class ModerationService:
    def __init__(
        self,
        repository: ModerationRepository,
        *,
        ai_client: ModerationAiClient | None,
        ocr_service: AttachmentOcrService | None = None,
        runtime_config: ModerationRuntimeConfig,
    ) -> None:
        self.repository = repository
        self.ai_client = ai_client
        self.ocr_service = ocr_service
        self.runtime_config = runtime_config

    def should_consider(self, message: discord.Message, *, addressed_to_bot: bool = False) -> bool:
        has_scannable_attachment = any(self._should_scan_attachment(item) for item in message.attachments)
        if self.ai_client is not None and self.ai_client.is_configured():
            if addressed_to_bot:
                return bool(message.content.strip() or has_scannable_attachment)
            return bool(message.content.strip() or has_scannable_attachment)
        if addressed_to_bot and not has_scannable_attachment:
            return should_consider_message_for_moderation(
                message.content,
                attachment_filenames=(attachment.filename for attachment in message.attachments),
                mention_count=len(message.mentions),
            )
        return should_consider_message_for_moderation(
            message.content,
            attachment_filenames=(attachment.filename for attachment in message.attachments),
            mention_count=len(message.mentions),
        )

    async def build_payload(
        self,
        message: discord.Message,
        *,
        reply_to_bot: bool = False,
        bot_mentioned: bool = False,
        addressed_to_bot: bool = False,
        author_is_protected: bool = False,
    ) -> ModerationEvaluationInput:
        recent_messages = list(await self._collect_recent_messages(message))
        attachment_ocr_texts = self._filter_meta_ocr_texts(await self._extract_attachment_ocr_texts(message))
        reference_context = self._build_reference_context(message)
        if reference_context is not None and not any(
            item.author_id == reference_context.author_id and item.created_at == reference_context.created_at and item.content == reference_context.content
            for item in recent_messages
        ):
            recent_messages.append(reference_context)
            recent_messages.sort(key=lambda item: item.created_at)

        guild_name = message.guild.name if message.guild else ""
        channel_name = getattr(message.channel, "name", str(message.channel))
        author_display_name = getattr(message.author, "display_name", message.author.name)
        role_names = _extract_role_names(message.author)

        known_profile = self.repository.get_known_profile(message.author.id)
        known_profile_summary = ""
        if known_profile is not None:
            alias_text = f" ({', '.join(known_profile.aliases)})" if known_profile.aliases else ""
            known_profile_summary = f"{known_profile.primary_name}{alias_text} - {known_profile.summary}"

        observed_character = ""
        recent_samples: tuple[str, ...] = ()
        history_snapshot = None
        if message.guild is not None:
            observed_character = self.repository.describe_user_character(guild_id=message.guild.id, user_id=message.author.id)
            recent_samples = self.repository.get_recent_user_samples(guild_id=message.guild.id, user_id=message.author.id)
            history_snapshot = self.repository.get_user_history_snapshot(guild_id=message.guild.id, user_id=message.author.id)

        return ModerationEvaluationInput(
            guild_id=message.guild.id if message.guild else 0,
            guild_name=guild_name,
            channel_id=message.channel.id,
            channel_name=channel_name,
            message_id=message.id,
            author_id=message.author.id,
            author_name=message.author.name,
            author_display_name=author_display_name,
            content=message.content,
            attachment_urls=tuple(attachment.url for attachment in message.attachments),
            attachment_filenames=tuple(attachment.filename for attachment in message.attachments),
            attachment_ocr_texts=attachment_ocr_texts,
            mention_count=len(message.mentions),
            recent_messages=tuple(recent_messages),
            server_rules=self.runtime_config.server_rules,
            server_facts=self.runtime_config.server_facts,
            reply_to_bot=reply_to_bot,
            bot_mentioned=bot_mentioned,
            addressed_to_bot=addressed_to_bot,
            author_is_protected=author_is_protected,
            author_role_names=role_names,
            author_known_profile=known_profile_summary,
            author_observed_character=observed_character,
            author_recent_samples=recent_samples,
            author_history=history_snapshot or ModerationHistorySnapshot(),
            known_people_directory=_build_known_people_directory(self.repository, message.guild),
            observed_people_directory=_build_observed_people_directory(
                self.repository,
                message.guild,
                recent_messages=recent_messages,
                message=message,
            ),
            target_subject_hint=_build_target_subject_hint(
                self.repository,
                message.guild,
                recent_messages=recent_messages,
                message=message,
            ),
            guild_staff_directory=_extract_live_staff_directory(message.guild),
            guild_channel_directory=_extract_live_channel_directory(message.guild),
            guild_role_directory=_extract_live_role_directory(message.guild),
        )

    def evaluate(self, payload: ModerationEvaluationInput) -> ModerationDecision:
        rule_decision = evaluate_with_rules(payload)
        ai_decision = None
        if self.ai_client is not None and self.ai_client.is_configured():
            ai_decision = self.ai_client.evaluate(payload)

        decision = choose_moderation_decision(
            payload=payload,
            rule_decision=rule_decision,
            ai_decision=ai_decision,
        )
        return ModerationDecision(
            decision=decision.decision,
            confidence=decision.confidence,
            reason=decision.reason,
            labels=decision.labels,
            timeout_minutes=decision.timeout_minutes,
            reply_text=self._trim_reply(decision.reply_text),
            source=decision.source,
            requires_admin_alert=decision.requires_admin_alert,
            should_delete_message=decision.should_delete_message,
            should_timeout_user=decision.should_timeout_user,
            reaction_emoji=self._trim_reaction(decision.reaction_emoji),
        )

    async def archive_decision(
        self,
        *,
        settings: ModerationGuildSettings,
        message: discord.Message,
        payload: ModerationEvaluationInput,
        decision: ModerationDecision,
    ) -> int | None:
        if message.guild is None:
            return None

        archive_channel = message.guild.get_channel(settings.archive_channel_id)
        if not isinstance(archive_channel, discord.TextChannel):
            try:
                archive_channel = await message.guild.fetch_channel(settings.archive_channel_id)
            except discord.HTTPException:
                return None
        if not isinstance(archive_channel, discord.TextChannel):
            return None

        context_lines = tuple(f"{item.author_name}: {item.content}" for item in payload.recent_messages if item.content.strip())
        embed = self._build_archive_embed(message=message, payload=payload, decision=decision)
        archive_message = await archive_channel.send(
            content=self._build_compact_archive_search_text(payload),
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.repository.add_event(
            ModerationEventRecord(
                guild_id=payload.guild_id,
                channel_id=payload.channel_id,
                message_id=payload.message_id,
                author_id=payload.author_id,
                author_name=payload.author_name,
                message_content=payload.content,
                decision=decision.decision,
                reason=decision.reason,
                labels=decision.labels,
                timeout_minutes=decision.timeout_minutes,
                source=decision.source,
                confidence=decision.confidence,
                archive_message_id=archive_message.id,
                reply_text=decision.reply_text,
                attachment_urls=payload.attachment_urls,
                context_lines=context_lines,
            )
        )
        return archive_message.id

    async def apply_member_timeout(self, member: discord.Member, *, timeout_minutes: int, reason: str) -> bool:
        if timeout_minutes <= 0:
            return False
        try:
            await member.timeout(timedelta(minutes=timeout_minutes), reason=reason[:512])
            return True
        except discord.HTTPException as error:
            logger.warning("Не удалось выдать timeout пользователю %s: %s", member.id, error)
            return False

    async def apply_member_ban(self, member: discord.Member, *, reason: str) -> bool:
        try:
            await member.ban(delete_message_seconds=0, reason=reason[:512])
            return True
        except discord.HTTPException as error:
            logger.warning("Не удалось забанить пользователя %s: %s", member.id, error)
            return False

    async def delete_message(self, message: discord.Message) -> bool:
        try:
            await message.delete()
            return True
        except discord.HTTPException as error:
            logger.warning("Не удалось удалить сообщение %s: %s", message.id, error)
            return False

    async def send_reply_text(self, message: discord.Message, reply_text: str) -> None:
        if not reply_text:
            return
        enriched_reply = self._enrich_reply_mentions(message.guild, reply_text, self.repository)
        try:
            await message.reply(
                enriched_reply,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False, replied_user=False),
            )
        except discord.HTTPException as error:
            logger.warning("Не удалось отправить reply в канал %s: %s", message.channel.id, error)
            try:
                await message.channel.send(
                    enriched_reply,
                    allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                )
            except discord.HTTPException as fallback_error:
                logger.warning("Не удалось отправить fallback-ответ в канал %s: %s", message.channel.id, fallback_error)

    async def send_reaction(self, message: discord.Message, reaction_emoji: str) -> bool:
        normalized = self._trim_reaction(reaction_emoji)
        if not normalized:
            return False
        try:
            await message.add_reaction(normalized)
            return True
        except discord.HTTPException as error:
            logger.warning("Не удалось поставить реакцию %s на сообщение %s: %s", normalized, message.id, error)
            return False

    async def send_public_reply(self, message: discord.Message, *, decision: ModerationDecision) -> None:
        if not decision.reply_text:
            return
        await self.send_reply_text(message, decision.reply_text)

    async def send_admin_alert(
        self,
        *,
        settings: ModerationGuildSettings,
        message: discord.Message,
        decision: ModerationDecision,
    ) -> None:
        mention = ""
        if settings.admin_alert_role_id is not None:
            mention = f"<@&{settings.admin_alert_role_id}>"
        elif settings.admin_alert_user_id is not None:
            mention = f"<@{settings.admin_alert_user_id}>"

        content_preview = message.content.strip() or "без текста"
        alert_text = (
            f"{mention} Похоже на рекламу или мутный промо-вброс.\n"
            f"Автор: <@{message.author.id}>\n"
            f"Причина: {decision.reason}\n"
            f"Сообщение: {content_preview[:400]}"
        ).strip()
        try:
            await message.reply(
                alert_text,
                mention_author=False,
                allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False, replied_user=False),
            )
        except discord.HTTPException as error:
            logger.warning("Не удалось отправить alert-reply в канал %s: %s", message.channel.id, error)

    def build_protected_reply_decision(
        self,
        *,
        author_id: int,
        display_name: str,
        decision: ModerationDecision,
    ) -> ModerationDecision:
        del author_id, display_name
        return build_protected_review(decision)

    def format_status_message(self, settings: ModerationGuildSettings | None) -> str:
        if settings is None:
            return "Автомодерация ещё не настроена. Укажи архивный канал через `/moderation setup`."

        admin_target = "не задан"
        if settings.admin_alert_role_id is not None:
            admin_target = f"<@&{settings.admin_alert_role_id}>"
        elif settings.admin_alert_user_id is not None:
            admin_target = f"<@{settings.admin_alert_user_id}>"

        return (
            "Автомодерация настроена.\n"
            f"Архив: <#{settings.archive_channel_id}>\n"
            f"Пинг модерации для рекламы: {admin_target}\n"
            f"AI endpoint: {'включён' if self.ai_client and self.ai_client.is_configured() else 'не настроен'}\n"
            f"Порог автодействия: {self.runtime_config.confidence_threshold:.2f}"
        )

    async def _collect_recent_messages(self, message: discord.Message) -> tuple[ModerationContextMessage, ...]:
        if not hasattr(message.channel, "history"):
            return ()

        items: list[ModerationContextMessage] = []
        try:
            async for item in message.channel.history(limit=self.runtime_config.candidate_window, before=message):
                if item.author.bot:
                    continue
                content = item.content.strip()
                if not content:
                    continue
                items.append(
                    ModerationContextMessage(
                        author_id=item.author.id,
                        author_name=getattr(item.author, "display_name", item.author.name),
                        content=content[:280],
                        created_at=int(item.created_at.timestamp()),
                        is_target_author=item.author.id == message.author.id,
                    )
                )
        except discord.HTTPException as error:
            logger.warning("Не удалось собрать контекст для сообщения %s: %s", message.id, error)
            return ()

        items.reverse()
        return tuple(items)

    def _build_reference_context(self, message: discord.Message) -> ModerationContextMessage | None:
        reference = message.reference
        if reference is None:
            return None
        referenced = reference.resolved if isinstance(reference.resolved, discord.Message) else getattr(reference, "cached_message", None)
        if not isinstance(referenced, discord.Message):
            return None
        content = referenced.content.strip()
        if not content:
            return None
        return ModerationContextMessage(
            author_id=referenced.author.id,
            author_name=getattr(referenced.author, "display_name", referenced.author.name),
            content=content[:280],
            created_at=int(referenced.created_at.timestamp()),
            is_target_author=referenced.author.id == message.author.id,
        )

    async def _extract_attachment_ocr_texts(self, message: discord.Message) -> tuple[str, ...]:
        if self.ocr_service is None or not message.attachments:
            return ()
        try:
            return await asyncio.to_thread(self.ocr_service.extract_texts, list(message.attachments))
        except Exception:
            logger.exception("Не удалось снять OCR с вложений сообщения %s.", message.id)
            return ()

    def _should_scan_attachment(self, attachment: discord.Attachment) -> bool:
        return self.ocr_service.should_scan_attachment(attachment) if self.ocr_service is not None else False

    def _filter_meta_ocr_texts(self, texts: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(text for text in texts if not looks_like_meta_moderation_ocr(text))

    def _trim_reply(self, reply_text: str) -> str:
        normalized = " ".join(reply_text.split()).strip()
        return normalized[: self.runtime_config.max_reply_length]

    def _trim_reaction(self, reaction_emoji: str) -> str:
        normalized = " ".join(reaction_emoji.split()).strip()
        return normalized[:32]

    def _build_archive_embed(
        self,
        *,
        message: discord.Message,
        payload: ModerationEvaluationInput,
        decision: ModerationDecision,
    ) -> discord.Embed:
        return build_archive_embed(message=message, payload=payload, decision=decision)

    def _build_compact_archive_search_text(self, payload: ModerationEvaluationInput) -> str:
        return build_compact_archive_search_text(payload)

    def _build_archive_search_text(self, payload: ModerationEvaluationInput) -> str:
        return build_archive_search_text(payload)

    def _enrich_reply_mentions(
        self,
        guild: discord.Guild | None,
        reply_text: str,
        repository: ModerationRepository,
    ) -> str:
        return enrich_reply_mentions(guild, reply_text, repository)


def _extract_role_names(member: discord.abc.User) -> tuple[str, ...]:
    roles = getattr(member, "roles", ())
    collected: list[str] = []
    for role in roles:
        name = getattr(role, "name", "").strip()
        if not name or name == "@everyone":
            continue
        collected.append(name)
    return tuple(collected[-8:])


def _classify_staff_member(member: discord.Member, guild: discord.Guild) -> tuple[str | None, int]:
    if member.id == guild.owner_id:
        return "владелец сервера", -1

    perms = member.guild_permissions
    if perms.administrator:
        return "администратор", 0
    if perms.manage_guild:
        return "управление сервером", 1
    if perms.moderate_members or perms.manage_messages:
        return "модератор", 2
    return None, 99


def _extract_live_staff_directory(guild: discord.Guild | None) -> tuple[str, ...]:
    if guild is None:
        return ()

    staff: list[tuple[int, str, str]] = []
    seen_ids: set[int] = set()
    for member in getattr(guild, "members", ()):
        if member.bot or member.id in seen_ids:
            continue
        tag, priority = _classify_staff_member(member, guild)
        if not tag:
            continue
        role_names = _extract_role_names(member)
        role_text = f"; роли: {', '.join(role_names[-4:])}" if role_names else ""
        staff.append((priority, member.display_name.casefold(), f"{member.display_name} -> <@{member.id}> - {tag}{role_text}"))
        seen_ids.add(member.id)

    staff.sort(key=lambda item: (item[0], item[1]))
    return tuple(item[2] for item in staff[:18])


def _extract_live_channel_directory(guild: discord.Guild | None) -> tuple[str, ...]:
    if guild is None:
        return ()

    channels: list[tuple[int, int, str]] = []
    for channel in getattr(guild, "channels", ()):
        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            continue
        topic = getattr(channel, "topic", None)
        suffix = f" - {topic.strip()[:80]}" if isinstance(topic, str) and topic.strip() else ""
        channels.append((getattr(channel, "position", 0), channel.id, f"#{channel.name} -> <#{channel.id}>{suffix}"))

    channels.sort(key=lambda item: (item[0], item[1]))
    return tuple(item[2] for item in channels[:24])


def _extract_live_role_directory(guild: discord.Guild | None) -> tuple[str, ...]:
    if guild is None:
        return ()

    entries: list[str] = []
    roles = sorted(getattr(guild, "roles", ()), key=lambda role: getattr(role, "position", 0), reverse=True)
    for role in roles:
        name = getattr(role, "name", "").strip()
        if not name or name == "@everyone" or getattr(role, "managed", False):
            continue
        entries.append(name)
        if len(entries) >= 24:
            break
    return tuple(entries)


def _build_known_people_directory(repository: ModerationRepository, guild: discord.Guild | None) -> tuple[str, ...]:
    profiles = repository.list_known_profiles(limit=16)
    if not profiles:
        return ()

    guild_members = {member.id: member for member in getattr(guild, "members", ())} if guild is not None else {}
    entries: list[str] = []
    for profile in profiles:
        alias_text = f" ({', '.join(profile.aliases)})" if profile.aliases else ""
        member = guild_members.get(profile.discord_id)
        display_name = getattr(member, "display_name", profile.primary_name)
        username = getattr(member, "name", "")
        username_text = f" (@{username})" if username and username != display_name else ""
        entries.append(f"{display_name}{alias_text}{username_text} -> <@{profile.discord_id}> - {profile.summary}")
    return tuple(entries)


def _build_observed_people_directory(
    repository: ModerationRepository,
    guild: discord.Guild | None,
    *,
    recent_messages: list[ModerationContextMessage],
    message: discord.Message,
) -> tuple[str, ...]:
    if guild is None:
        return ()

    guild_members = {member.id: member for member in getattr(guild, "members", ())}
    candidate_ids: list[int] = []

    for mentioned in getattr(message, "mentions", ()):
        mentioned_id = getattr(mentioned, "id", None)
        if isinstance(mentioned_id, int) and mentioned_id != message.author.id:
            candidate_ids.append(mentioned_id)

    for item in recent_messages:
        if item.author_id != message.author.id:
            candidate_ids.append(item.author_id)

    seen_ids: set[int] = set()
    entries: list[str] = []
    for user_id in candidate_ids:
        if user_id in seen_ids:
            continue
        seen_ids.add(user_id)

        known_profile = repository.get_known_profile(user_id)
        observed_summary = repository.describe_user_character(guild_id=guild.id, user_id=user_id)
        if not known_profile and not observed_summary:
            continue

        member = guild_members.get(user_id)
        display_name = getattr(member, "display_name", None)
        if not display_name:
            display_name = known_profile.primary_name if known_profile is not None else str(user_id)
        username = getattr(member, "name", "")
        alias_pool = []
        if known_profile is not None:
            alias_pool.extend(alias for alias in known_profile.aliases if alias)
        if username and username != display_name:
            alias_pool.append(f"@{username}")
        alias_text = f" ({', '.join(dict.fromkeys(alias_pool))})" if alias_pool else ""

        role_names = _extract_role_names(member) if member is not None else ()
        role_text = f"; роли: {', '.join(role_names[-4:])}" if role_names else ""
        summary_parts: list[str] = []
        if known_profile is not None:
            summary_parts.append(known_profile.summary)
        if observed_summary and observed_summary not in summary_parts:
            summary_parts.append(observed_summary)
        summary_text = " | ".join(part for part in summary_parts if part)
        if not summary_text:
            continue

        entries.append(f"{display_name}{alias_text} -> <@{user_id}> - {summary_text}{role_text}")
        if len(entries) >= 10:
            break

    return tuple(entries)


_WHO_IS_RE = re.compile(r"\bкто\s+(?:это|такой|такая)\b", re.IGNORECASE)


def _build_target_subject_hint(
    repository: ModerationRepository,
    guild: discord.Guild | None,
    *,
    recent_messages: list[ModerationContextMessage],
    message: discord.Message,
) -> str:
    if guild is None:
        return ""

    content = (message.content or "").strip()
    normalized_content = _normalize_lookup_text(content)
    if not normalized_content:
        return ""

    should_scan_members = bool(_WHO_IS_RE.search(content))
    candidate_ids: list[int] = []

    for mentioned in getattr(message, "mentions", ()):
        mentioned_id = getattr(mentioned, "id", None)
        if isinstance(mentioned_id, int):
            candidate_ids.append(mentioned_id)

    for item in recent_messages:
        candidate_ids.append(item.author_id)

    if should_scan_members:
        candidate_ids.extend(member.id for member in getattr(guild, "members", ()) if not getattr(member, "bot", False))

    guild_members = {member.id: member for member in getattr(guild, "members", ())}
    snapshots = {snapshot.user_id: snapshot for snapshot in repository.list_user_observation_snapshots(guild_id=guild.id, minimum_messages=1)}

    best_match: tuple[int, int, str] | None = None
    seen_ids: set[int] = set()
    for user_id in candidate_ids:
        if user_id in seen_ids or user_id == message.author.id:
            continue
        seen_ids.add(user_id)

        member = guild_members.get(user_id)
        known_profile = repository.get_known_profile(user_id)
        snapshot = snapshots.get(user_id)
        aliases = _build_member_aliases(member, known_profile, snapshot)
        for alias in aliases:
            normalized_alias = _normalize_lookup_text(alias)
            if len(normalized_alias) < 3:
                continue
            if normalized_alias and normalized_alias in normalized_content:
                score = len(normalized_alias)
                if best_match is None or score > best_match[0]:
                    best_match = (score, user_id, alias)

    if best_match is None:
        return ""

    user_id = best_match[1]
    member = guild_members.get(user_id)
    known_profile = repository.get_known_profile(user_id)
    observed_summary = repository.describe_user_character(guild_id=guild.id, user_id=user_id)
    snapshot = snapshots.get(user_id)

    display_name = getattr(member, "display_name", None) or (snapshot.display_name if snapshot is not None else "")
    if not display_name:
        display_name = known_profile.primary_name if known_profile is not None else str(user_id)

    username = getattr(member, "name", "")
    role_names = _extract_role_names(member) if member is not None else (snapshot.role_names if snapshot is not None else ())
    role_text = f"; роли: {', '.join(role_names[-4:])}" if role_names else ""
    parts = []
    if known_profile is not None:
        parts.append(known_profile.summary)
    if observed_summary and observed_summary not in parts:
        parts.append(observed_summary)
    if not parts and snapshot is not None and snapshot.recent_samples:
        parts.append(snapshot.recent_samples[-1])
    summary_text = " | ".join(part for part in parts if part)
    if not summary_text:
        summary_text = "участник текущего разговора"

    alias_pool = [alias for alias in _build_member_aliases(member, known_profile, snapshot) if alias and alias != display_name]
    alias_text = f" (алиасы: {', '.join(dict.fromkeys(alias_pool[:6]))})" if alias_pool else ""
    username_text = f" (@{username})" if username and username != display_name else ""
    return f"{display_name}{username_text}{alias_text} -> <@{user_id}> - {summary_text}{role_text}"


def _build_member_aliases(
    member: discord.Member | None,
    known_profile,
    snapshot,
) -> tuple[str, ...]:
    aliases: list[str] = []
    for raw in (
        getattr(member, "display_name", ""),
        getattr(member, "name", ""),
        getattr(known_profile, "primary_name", ""),
        *(getattr(known_profile, "aliases", ()) or ()),
        getattr(snapshot, "display_name", ""),
    ):
        text = str(raw).strip()
        if text:
            aliases.append(text)
    expanded: list[str] = []
    for alias in aliases:
        expanded.append(alias)
        transliterated = _latin_to_cyrillic_alias(alias)
        if transliterated and transliterated.casefold() != alias.casefold():
            expanded.append(transliterated)
    return tuple(dict.fromkeys(expanded))


def _normalize_lookup_text(text: str) -> str:
    lowered = text.casefold()
    lowered = re.sub(r"<@!?\d+>|<@&\d+>", " ", lowered)
    lowered = re.sub(r"[^\wа-яё]+", " ", lowered, flags=re.IGNORECASE)
    return " ".join(lowered.split()).strip()


_LATIN_TO_CYRILLIC_DIGRAPHS = (
    ("shch", "щ"),
    ("sch", "щ"),
    ("yo", "ё"),
    ("zh", "ж"),
    ("kh", "х"),
    ("ts", "ц"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("yu", "ю"),
    ("ya", "я"),
    ("ye", "е"),
)

_LATIN_TO_CYRILLIC_CHARS = {
    "a": "а",
    "b": "б",
    "c": "к",
    "d": "д",
    "e": "е",
    "f": "ф",
    "g": "г",
    "h": "х",
    "i": "и",
    "j": "дж",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "o": "о",
    "p": "п",
    "q": "к",
    "r": "р",
    "s": "с",
    "t": "т",
    "u": "у",
    "v": "в",
    "w": "в",
    "x": "кс",
    "y": "й",
    "z": "з",
}


def _latin_to_cyrillic_alias(text: str) -> str:
    if not text or not any("a" <= char.casefold() <= "z" for char in text):
        return ""

    lowered = text.casefold()
    result: list[str] = []
    index = 0
    while index < len(lowered):
        matched = False
        for latin, cyrillic in _LATIN_TO_CYRILLIC_DIGRAPHS:
            if lowered.startswith(latin, index):
                result.append(cyrillic)
                index += len(latin)
                matched = True
                break
        if matched:
            continue

        char = lowered[index]
        if char in _LATIN_TO_CYRILLIC_CHARS:
            result.append(_LATIN_TO_CYRILLIC_CHARS[char])
        else:
            result.append(char)
        index += 1

    return "".join(result)


def _enrich_reply_mentions(guild: discord.Guild | None, reply_text: str, repository: ModerationRepository) -> str:
    return enrich_reply_mentions(guild, reply_text, repository)
