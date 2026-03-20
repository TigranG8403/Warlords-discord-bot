from __future__ import annotations

from .config import ModerationDecision, ModerationEvaluationInput


_DECISION_PRIORITY = {
    "allow": 0,
    "review": 1,
    "warning": 2,
    "scam_alert": 3,
    "light_violation": 4,
    "ban_violation": 5,
}

_MECHANICAL_LABELS = {
    "advertising",
    "casino",
    "flood",
    "ocr",
    "promo",
    "scam",
    "spam",
}


def choose_moderation_decision(
    *,
    payload: ModerationEvaluationInput,
    rule_decision: ModerationDecision,
    ai_decision: ModerationDecision | None,
) -> ModerationDecision:
    if ai_decision is None:
        return apply_operational_policy(rule_decision)

    if should_override_ai_with_rules(rule_decision=rule_decision, ai_decision=ai_decision):
        chosen = merge_rule_override(rule_decision=rule_decision, ai_decision=ai_decision)
    else:
        chosen = ai_decision

    chosen = soften_low_signal_review(payload=payload, decision=chosen)
    chosen = apply_warning_policy(payload=payload, decision=chosen)
    return apply_operational_policy(chosen)


def apply_operational_policy(decision: ModerationDecision) -> ModerationDecision:
    name = decision.decision
    timeout_minutes = max(0, int(decision.timeout_minutes))
    requires_admin_alert = bool(decision.requires_admin_alert)
    should_delete_message = bool(decision.should_delete_message)
    should_timeout_user = bool(decision.should_timeout_user)

    if name == "allow":
        timeout_minutes = 0
        requires_admin_alert = False
        should_delete_message = False
        should_timeout_user = False
    elif name == "review":
        timeout_minutes = 0
        requires_admin_alert = False
        should_delete_message = False
        should_timeout_user = False
    elif name == "warning":
        timeout_minutes = 0
        requires_admin_alert = False
        should_delete_message = False
        should_timeout_user = False
    elif name == "scam_alert":
        timeout_minutes = 0
        requires_admin_alert = True
        should_delete_message = False
        should_timeout_user = False
    elif name == "light_violation":
        if timeout_minutes <= 0:
            timeout_minutes = 60
        requires_admin_alert = False
        should_delete_message = True
        should_timeout_user = True
    elif name == "ban_violation":
        timeout_minutes = 0
        requires_admin_alert = False
        should_delete_message = True
        should_timeout_user = False

    return ModerationDecision(
        decision=name,
        confidence=decision.confidence,
        reason=decision.reason,
        labels=decision.labels,
        timeout_minutes=timeout_minutes,
        reply_text=decision.reply_text,
        source=decision.source,
        requires_admin_alert=requires_admin_alert,
        should_delete_message=should_delete_message,
        should_timeout_user=should_timeout_user,
        reaction_emoji=decision.reaction_emoji,
    )


def build_protected_review(decision: ModerationDecision) -> ModerationDecision:
    labels = decision.labels + (("protected_member",) if "protected_member" not in decision.labels else ())
    return ModerationDecision(
        decision="review",
        confidence=decision.confidence,
        reason=f"{decision.reason} Санкция не применена: пользователь выше бота по роли.",
        labels=labels,
        timeout_minutes=0,
        reply_text=decision.reply_text,
        source=decision.source,
        requires_admin_alert=False,
        should_delete_message=False,
        should_timeout_user=False,
        reaction_emoji=decision.reaction_emoji,
    )


def should_override_ai_with_rules(
    *,
    rule_decision: ModerationDecision,
    ai_decision: ModerationDecision,
) -> bool:
    if rule_decision.decision == "allow":
        return False
    if not is_mechanical_rule(rule_decision):
        return False
    if _priority(rule_decision.decision) > _priority(ai_decision.decision):
        return True
    if ai_decision.decision == "allow":
        return True
    if rule_decision.decision == "scam_alert" and ai_decision.decision == "review":
        return True
    return False


def merge_rule_override(
    *,
    rule_decision: ModerationDecision,
    ai_decision: ModerationDecision,
) -> ModerationDecision:
    return ModerationDecision(
        decision=rule_decision.decision,
        confidence=rule_decision.confidence,
        reason=rule_decision.reason,
        labels=rule_decision.labels,
        timeout_minutes=rule_decision.timeout_minutes,
        reply_text=ai_decision.reply_text or rule_decision.reply_text,
        source=rule_decision.source,
        requires_admin_alert=rule_decision.requires_admin_alert,
        should_delete_message=rule_decision.should_delete_message,
        should_timeout_user=rule_decision.should_timeout_user,
        reaction_emoji=ai_decision.reaction_emoji or rule_decision.reaction_emoji,
    )


def is_mechanical_rule(decision: ModerationDecision) -> bool:
    labels = {label.casefold() for label in decision.labels}
    return bool(labels & _MECHANICAL_LABELS)


def soften_low_signal_review(
    *,
    payload: ModerationEvaluationInput,
    decision: ModerationDecision,
) -> ModerationDecision:
    if decision.decision != "review":
        return decision
    if decision.labels or decision.confidence >= 0.55:
        return decision
    if payload.attachment_filenames or payload.attachment_ocr_texts:
        return decision
    if any(marker in payload.content.lower() for marker in ("http://", "https://", "discord.gg/", "t.me/", "vk.com/")):
        return decision
    if len(payload.content.strip()) > 90:
        return decision
    return ModerationDecision(
        decision="allow",
        confidence=decision.confidence,
        reason=f"{decision.reason} Сигнал слишком слабый, поэтому без вмешательства.",
        labels=decision.labels,
        timeout_minutes=0,
        reply_text=decision.reply_text,
        source=decision.source,
        requires_admin_alert=False,
        should_delete_message=False,
        should_timeout_user=False,
        reaction_emoji=decision.reaction_emoji,
    )


def apply_warning_policy(
    *,
    payload: ModerationEvaluationInput,
    decision: ModerationDecision,
) -> ModerationDecision:
    if decision.decision == "warning":
        return escalate_repeated_warning(payload=payload, decision=decision)
    if decision.decision == "light_violation":
        return strengthen_repeated_timeout(payload=payload, decision=decision)
    return decision


def escalate_repeated_warning(
    *,
    payload: ModerationEvaluationInput,
    decision: ModerationDecision,
) -> ModerationDecision:
    history = payload.author_history
    repeated_warning = 0 <= history.last_warning_age_minutes <= 12 * 60
    repeated_labels = bool(
        history.last_labels
        and decision.labels
        and set(label.casefold() for label in history.last_labels) & set(label.casefold() for label in decision.labels)
        and 0 <= history.last_event_age_minutes <= 24 * 60
    )
    prior_sanction = 0 <= history.last_sanction_age_minutes <= 72 * 60

    if not (
        repeated_warning
        or repeated_labels
        or history.warning_count_24h >= 2
        or history.light_violation_count_72h >= 1
        or history.ban_violation_count_30d >= 1
        or prior_sanction
    ):
        return decision

    timeout_minutes = 60
    if history.ban_violation_count_30d >= 1 or history.light_violation_count_72h >= 1 or prior_sanction:
        timeout_minutes = 180
    elif repeated_warning or repeated_labels or history.warning_count_24h >= 2:
        timeout_minutes = 90

    return ModerationDecision(
        decision="light_violation",
        confidence=max(decision.confidence, 0.72),
        reason=(
            f"{decision.reason} Повтор после недавнего предупреждения, поэтому устным замечанием уже не отделаться."
        ).strip(),
        labels=decision.labels + (("warning_escalation",) if "warning_escalation" not in decision.labels else ()),
        timeout_minutes=max(timeout_minutes, int(decision.timeout_minutes)),
        reply_text=decision.reply_text,
        source=decision.source,
        requires_admin_alert=False,
        should_delete_message=True,
        should_timeout_user=True,
        reaction_emoji=decision.reaction_emoji,
    )


def strengthen_repeated_timeout(
    *,
    payload: ModerationEvaluationInput,
    decision: ModerationDecision,
) -> ModerationDecision:
    history = payload.author_history
    timeout_minutes = max(0, int(decision.timeout_minutes))
    minimum_timeout = timeout_minutes

    if history.light_violation_count_72h >= 1:
        minimum_timeout = max(minimum_timeout, 180)
    elif history.warning_count_24h >= 2 or (0 <= history.last_warning_age_minutes <= 12 * 60):
        minimum_timeout = max(minimum_timeout, 90)

    if history.ban_violation_count_30d >= 1:
        minimum_timeout = max(minimum_timeout, 240)

    if minimum_timeout == timeout_minutes:
        return decision

    return ModerationDecision(
        decision=decision.decision,
        confidence=decision.confidence,
        reason=decision.reason,
        labels=decision.labels,
        timeout_minutes=minimum_timeout,
        reply_text=decision.reply_text,
        source=decision.source,
        requires_admin_alert=decision.requires_admin_alert,
        should_delete_message=decision.should_delete_message,
        should_timeout_user=decision.should_timeout_user,
        reaction_emoji=decision.reaction_emoji,
    )


def _priority(decision_name: str) -> int:
    return _DECISION_PRIORITY.get(decision_name, 0)
