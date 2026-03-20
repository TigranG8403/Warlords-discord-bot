from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ModerationGuildSettings:
    guild_id: int
    archive_channel_id: int
    admin_alert_role_id: int | None = None
    admin_alert_user_id: int | None = None


@dataclass(slots=True)
class ModerationKnownProfile:
    discord_id: int
    primary_name: str
    aliases: tuple[str, ...] = ()
    summary: str = ""


@dataclass(slots=True)
class ModerationUserObservationSnapshot:
    guild_id: int
    user_id: int
    display_name: str
    role_names: tuple[str, ...] = ()
    recent_samples: tuple[str, ...] = ()
    total_messages: int = 0


@dataclass(slots=True)
class ModerationContextMessage:
    author_id: int
    author_name: str
    content: str
    created_at: int
    is_target_author: bool = False


@dataclass(slots=True)
class ModerationHistorySnapshot:
    warning_count_24h: int = 0
    warning_count_72h: int = 0
    light_violation_count_72h: int = 0
    ban_violation_count_30d: int = 0
    last_decision: str = ""
    last_reason: str = ""
    last_labels: tuple[str, ...] = ()
    last_timeout_minutes: int = 0
    last_event_age_minutes: int = -1
    last_warning_age_minutes: int = -1
    last_sanction_age_minutes: int = -1
    recent_events: tuple[str, ...] = ()


@dataclass(slots=True)
class ModerationEvaluationInput:
    guild_id: int
    guild_name: str
    channel_id: int
    channel_name: str
    message_id: int
    author_id: int
    author_name: str
    author_display_name: str
    content: str
    attachment_urls: tuple[str, ...] = ()
    attachment_filenames: tuple[str, ...] = ()
    attachment_ocr_texts: tuple[str, ...] = ()
    mention_count: int = 0
    recent_messages: tuple[ModerationContextMessage, ...] = ()
    server_rules: tuple[str, ...] = ()
    server_facts: tuple[str, ...] = ()
    reply_to_bot: bool = False
    bot_mentioned: bool = False
    addressed_to_bot: bool = False
    author_is_protected: bool = False
    author_role_names: tuple[str, ...] = ()
    author_known_profile: str = ""
    author_observed_character: str = ""
    author_recent_samples: tuple[str, ...] = ()
    author_history: ModerationHistorySnapshot = field(default_factory=ModerationHistorySnapshot)
    known_people_directory: tuple[str, ...] = ()
    observed_people_directory: tuple[str, ...] = ()
    target_subject_hint: str = ""
    guild_staff_directory: tuple[str, ...] = ()
    guild_channel_directory: tuple[str, ...] = ()
    guild_role_directory: tuple[str, ...] = ()


@dataclass(slots=True)
class ModerationDecision:
    decision: str
    confidence: float
    reason: str
    labels: tuple[str, ...] = ()
    timeout_minutes: int = 0
    reply_text: str = ""
    source: str = "rules"
    requires_admin_alert: bool = False
    should_delete_message: bool = False
    should_timeout_user: bool = False
    reaction_emoji: str = ""


@dataclass(slots=True)
class ModerationEventRecord:
    guild_id: int
    channel_id: int
    message_id: int
    author_id: int
    author_name: str
    message_content: str
    decision: str
    reason: str
    labels: tuple[str, ...]
    timeout_minutes: int
    source: str
    confidence: float
    archive_message_id: int | None = None
    created_at: int = 0
    reply_text: str = ""
    attachment_urls: tuple[str, ...] = ()
    context_lines: tuple[str, ...] = ()


@dataclass(slots=True)
class ModerationRuntimeConfig:
    candidate_window: int = 6
    ai_url: str = ""
    ai_token: str = ""
    ai_timeout_seconds: int = 12
    confidence_threshold: float = 0.78
    max_reply_length: int = 220
    server_rules: tuple[str, ...] = field(default_factory=tuple)
    server_facts: tuple[str, ...] = field(default_factory=tuple)
