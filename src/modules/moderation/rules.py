from __future__ import annotations

import re
from typing import Iterable

from .config import ModerationDecision, ModerationEvaluationInput


URL_RE = re.compile(r"https?://\S+|discord\.gg/\S+|t\.me/\S+|vk\.com/\S+", re.IGNORECASE)
MENTION_SPAM_RE = re.compile(r"(<@!?\d+>|@everyone|@here)")
LONG_REPEAT_RE = re.compile(r"(.)\1{7,}")
REPEATED_WORDS_RE = re.compile(r"\b(\w+)(?:\s+\1){3,}\b", re.IGNORECASE)
PROFANITY_RE = re.compile(r"(нахуй|хуй|хуйн|пизд|ебан|ебл|уеб|уёб|залуп|высрал|высрал)", re.IGNORECASE)
HARD_INSULT_RE = re.compile(r"(долбо[её]б|еблан|у[её]бок|хуесос|мраз[ьй]|пидор|гнида|чмо|тварь|шлюха|урод|дегенерат|ублюдок)", re.IGNORECASE)
DIRECT_TARGET_RE = re.compile(r"(^|[\s,.;:!?])(ты|тебя|тебе|твой|твоя|твоё|иди|пош[её]л|сдохни|заткнись|завали|<@!?\d+>)(?=$|[\s,.;:!?])", re.IGNORECASE)
HATE_GROUP_RE = re.compile(r"(евре[йяе]|иуде|мусульман|ислам|христиан|православ|католик|буддист|религи)", re.IGNORECASE)
VIOLENT_VERB_RE = re.compile(r"(сжечь|жечь|убить|резать|повес|замуч|уничтож)", re.IGNORECASE)

CASINO_PROMO_RE = re.compile(
    r"(casino|казино|ставк|букмек|slot|слот|рулетк|bet|1win|1xbet|джекпот|bonus|promo(?: ?code)?|withdraw)",
    re.IGNORECASE,
)
SCAM_PROMO_RE = re.compile(
    r"(free nitro|нитро|airdrop|wallet|seed phrase|сид фраз|crypto|крипт|реферал|рефк|"
    r"фишинг|carding|кардинг|дроп|пробив|обнал|темка|схема заработка)",
    re.IGNORECASE,
)
AD_PROMO_RE = re.compile(
    r"(наш сервер|мой сервер|наш проект|мой проект|заходи к нам|вступай|подпишись|"
    r"розыгрыш|конкурс|переходи|ищем людей|ищу людей|услуги|магазин|продам|купите)",
    re.IGNORECASE,
)

OCR_BRAND_RE = re.compile(
    r"\b(1win|1xbet|mell(?:i|s)?troy\w*|meli(?:coins)?|mel(?:l|t)\s?coins?|cenatwin|mostbet|fonbet|pari|stake)\b|меллстрой",
    re.IGNORECASE,
)
OCR_CASINO_SIGNAL_RE = re.compile(
    r"\b(casino|казино|bonus(?:es)?|promo(?: ?code)?|activate code|vip-?club|rakeback|reward|claim)\b|бонус|промокод",
    re.IGNORECASE,
)
OCR_FINANCE_SIGNAL_RE = re.compile(
    r"\b(withdraw(?:al)?|deposit|wallet|balance|verification|transactions?|transfer|success|receive(?:d)?|instant(?:ly)?|crypto)\b|"
    r"вывод|выплат|депозит|кошел|баланс|вериф|транзак|крипт|попол",
    re.IGNORECASE,
)
OCR_PROMO_SIGNAL_RE = re.compile(
    r"\b(register(?:s|ed|ing)?|promo(?: ?code)?|activate|claim|reward|giveaway|bonus)\b|регист|промокод|получи|бонус",
    re.IGNORECASE,
)
OCR_DOMAIN_RE = re.compile(r"\b[a-z0-9-]{4,}\.(?:com|net|org|io|gg)\b", re.IGNORECASE)
OCR_AMOUNT_RE = re.compile(r"[$€₽]\s?\d|\b\d[\d,.]{2,}\s?(?:usd|eur|rub|руб|р)\b", re.IGNORECASE)


def should_consider_message_for_moderation(
    message_content: str,
    *,
    attachment_filenames: Iterable[str] = (),
    mention_count: int = 0,
) -> bool:
    content = message_content.strip()
    filenames = tuple(attachment_filenames)

    if not content and not filenames:
        return False
    if any(name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")) for name in filenames):
        return True
    if mention_count >= 3 or len(MENTION_SPAM_RE.findall(content)) >= 3:
        return True
    if LONG_REPEAT_RE.search(content) or REPEATED_WORDS_RE.search(content):
        return True
    if _looks_like_direct_insult(content) or _looks_like_hate_violence(content):
        return True
    if URL_RE.search(content) and (CASINO_PROMO_RE.search(content) or SCAM_PROMO_RE.search(content) or AD_PROMO_RE.search(content)):
        return True
    return False


def evaluate_with_rules(payload: ModerationEvaluationInput) -> ModerationDecision:
    content = payload.content.strip().lower()

    if _looks_like_bannable_attachment_ocr(payload):
        return ModerationDecision(
            decision="ban_violation",
            confidence=0.97,
            reason="OCR на вложениях очень похож на казино, скам или бонусную разводку.",
            labels=("scam", "casino", "ocr"),
            source="rules",
            should_delete_message=True,
        )

    if _looks_like_bannable_promo(payload):
        return ModerationDecision(
            decision="ban_violation",
            confidence=0.97,
            reason="Это похоже на казино, фишинг или откровенный скам.",
            labels=("scam", "promo"),
            source="rules",
            should_delete_message=True,
        )

    if _looks_like_advertising(payload):
        return ModerationDecision(
            decision="scam_alert",
            confidence=0.9,
            reason="Это похоже на рекламу или внешний промо-вброс.",
            labels=("advertising",),
            source="rules",
            requires_admin_alert=True,
        )

    if _looks_like_spam(payload):
        return ModerationDecision(
            decision="light_violation",
            confidence=0.86,
            reason="Похоже на флуд, спам или бессмысленный массовый шум.",
            labels=("spam",),
            timeout_minutes=60,
            source="rules",
            should_delete_message=True,
            should_timeout_user=True,
        )

    if _looks_like_hate_violence(content):
        return ModerationDecision(
            decision="ban_violation",
            confidence=0.95,
            reason="Есть явный призыв к насилию против группы людей.",
            labels=("violence", "religion_attack"),
            source="rules",
            should_delete_message=True,
        )

    if _looks_like_direct_insult(content):
        return ModerationDecision(
            decision="light_violation",
            confidence=0.9,
            reason="Есть прямое жёсткое оскорбление человека.",
            labels=("insult",),
            timeout_minutes=180,
            source="rules",
            should_delete_message=True,
            should_timeout_user=True,
        )

    return ModerationDecision(
        decision="allow",
        confidence=0.2,
        reason="Явных механических нарушений не найдено.",
        source="rules",
    )


def _looks_like_bannable_promo(payload: ModerationEvaluationInput) -> bool:
    content = payload.content
    if not URL_RE.search(content):
        return False
    return bool(CASINO_PROMO_RE.search(content) or SCAM_PROMO_RE.search(content))


def _looks_like_bannable_attachment_ocr(payload: ModerationEvaluationInput) -> bool:
    if not payload.attachment_ocr_texts:
        return False

    normalized = " ".join(payload.attachment_ocr_texts).lower()
    brand_hits = _count_unique_matches(OCR_BRAND_RE, normalized)
    casino_hits = _count_unique_matches(OCR_CASINO_SIGNAL_RE, normalized)
    finance_hits = _count_unique_matches(OCR_FINANCE_SIGNAL_RE, normalized)
    promo_hits = _count_unique_matches(OCR_PROMO_SIGNAL_RE, normalized)
    has_domain = OCR_DOMAIN_RE.search(normalized) is not None
    has_amount = OCR_AMOUNT_RE.search(normalized) is not None

    if brand_hits and (casino_hits or promo_hits or finance_hits >= 2 or has_domain):
        return True
    if brand_hits and finance_hits >= 1 and (has_amount or "balance" in normalized):
        return True
    if casino_hits >= 2 and (promo_hits >= 1 or finance_hits >= 1):
        return True
    if promo_hits >= 2 and finance_hits >= 2:
        return True
    if "withdrawal success" in normalized and has_amount:
        return True
    if any(phrase in normalized for phrase in ("claim your reward", "activate code", "promo code")) and (
        casino_hits or finance_hits >= 1 or has_domain
    ):
        return True
    if finance_hits >= 3 and has_amount and ("crypto" in normalized or promo_hits >= 1):
        return True
    return False


def _looks_like_advertising(payload: ModerationEvaluationInput) -> bool:
    content = payload.content
    if not URL_RE.search(content):
        return False
    if _looks_like_bannable_promo(payload):
        return False
    return bool(AD_PROMO_RE.search(content))


def _looks_like_spam(payload: ModerationEvaluationInput) -> bool:
    content = payload.content
    if len(MENTION_SPAM_RE.findall(content)) >= 3:
        return True
    if LONG_REPEAT_RE.search(content) or REPEATED_WORDS_RE.search(content):
        return True
    if len(set(filter(None, content.split()))) == 1 and len(content.split()) >= 4:
        return True

    recent_author_messages = [item.content.strip().lower() for item in payload.recent_messages if item.author_id == payload.author_id]
    if not recent_author_messages:
        return False

    normalized = content.strip().lower()
    duplicates = sum(1 for item in recent_author_messages if item == normalized)
    return duplicates >= 2


def _looks_like_direct_insult(content: str) -> bool:
    if HARD_INSULT_RE.search(content) and DIRECT_TARGET_RE.search(content):
        return True
    return bool(PROFANITY_RE.search(content) and DIRECT_TARGET_RE.search(content))


def _looks_like_hate_violence(content: str) -> bool:
    return bool(HATE_GROUP_RE.search(content) and VIOLENT_VERB_RE.search(content))


def _count_unique_matches(pattern: re.Pattern[str], text: str) -> int:
    return len({match.group(0).strip().lower() for match in pattern.finditer(text)})
