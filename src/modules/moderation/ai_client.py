from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import ModerationDecision, ModerationEvaluationInput
from .prompts import build_moderation_messages, build_persona_messages


@dataclass(slots=True)
class PersonaResponse:
    reply_text: str = ""
    reaction_emoji: str = ""


class ModerationAiClient:
    def __init__(
        self,
        *,
        provider: str = "",
        base_url: str,
        shared_token: str = "",
        api_key: str = "",
        model: str = "",
        timeout_seconds: int = 12,
    ) -> None:
        self.provider = provider.strip().lower() or ("deepseek" if api_key.strip() else "proxy")
        self.base_url = base_url.rstrip("/")
        self.shared_token = shared_token.strip()
        self.api_key = api_key.strip()
        self.model = model.strip() or "deepseek-chat"
        self.timeout_seconds = max(1, timeout_seconds)

    def is_configured(self) -> bool:
        if self.provider == "deepseek":
            return bool(self.api_key and self.base_url)
        return bool(self.base_url and self.shared_token)

    def supports_persona(self) -> bool:
        return self.provider == "deepseek" and self.is_configured()

    def evaluate(self, payload: ModerationEvaluationInput) -> ModerationDecision | None:
        if not self.is_configured():
            return None
        if self.provider == "deepseek":
            return self._evaluate_with_deepseek(payload)
        return self._evaluate_with_proxy(payload)

    def generate_persona_response(
        self,
        *,
        payload: ModerationEvaluationInput,
        previous_user_content: str,
        previous_bot_reply: str,
        recent_channel_replies: tuple[str, ...] = (),
    ) -> PersonaResponse | None:
        if not self.supports_persona():
            return None

        response = self._request_persona_response(
            payload=payload,
            previous_user_content=previous_user_content,
            previous_bot_reply=previous_bot_reply,
            recent_channel_replies=recent_channel_replies,
            force_reply=False,
        )
        if response is not None and (response.reply_text or response.reaction_emoji):
            return response
        if not payload.addressed_to_bot or not payload.content.strip():
            return response
        forced_response = self._request_persona_response(
            payload=payload,
            previous_user_content=previous_user_content,
            previous_bot_reply=previous_bot_reply,
            recent_channel_replies=recent_channel_replies,
            force_reply=True,
        )
        if forced_response is not None and (forced_response.reply_text or forced_response.reaction_emoji):
            return forced_response
        plain_reply = self._request_persona_plain_reply(
            payload=payload,
            previous_user_content=previous_user_content,
            previous_bot_reply=previous_bot_reply,
            recent_channel_replies=recent_channel_replies,
        )
        if plain_reply:
            return PersonaResponse(reply_text=plain_reply, reaction_emoji="")
        fallback = _build_direct_greeting_fallback(payload.content)
        if fallback is not None:
            return fallback
        return forced_response

    def generate_persona_reply(
        self,
        *,
        payload: ModerationEvaluationInput,
        previous_user_content: str,
        previous_bot_reply: str,
        recent_channel_replies: tuple[str, ...] = (),
    ) -> str | None:
        response = self.generate_persona_response(
            payload=payload,
            previous_user_content=previous_user_content,
            previous_bot_reply=previous_bot_reply,
            recent_channel_replies=recent_channel_replies,
        )
        if response is None:
            return None
        return response.reply_text or None

    def generate_user_character_summary(
        self,
        *,
        display_name: str,
        role_names: tuple[str, ...],
        known_profile: str,
        recent_samples: tuple[str, ...],
        existing_summary: str,
    ) -> str | None:
        if not self.supports_persona() or len(recent_samples) < 2:
            return None

        roles_line = ", ".join(role_names) if role_names else "нет заметных ролей"
        samples_text = "\n".join(f"- {item}" for item in recent_samples[-10:])
        content = self._deepseek_chat_completion(
            {
                "model": self.model,
                "temperature": 0.25,
                "max_tokens": 150,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Сделай короткую рабочую сводку о пользователе для другого бота. "
                            "Опирайся только на роли, известный профиль и реальные примеры сообщений. "
                            "Нужно не только про тон, но и про типичные темы, манеру общения с ботом и заметные привычки в чате. "
                            "Не выдумывай психологию, диагнозы и скрытые мотивы. "
                            "Одна компактная фраза, до 200 символов."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Пользователь: {display_name}\n"
                            f"Роли: {roles_line}\n"
                            f"Известный профиль: {known_profile or 'нет'}\n"
                            f"Текущая сводка: {existing_summary or 'нет'}\n"
                            f"Примеры общения:\n{samples_text}"
                        ),
                    },
                ],
            }
        )
        if not content:
            return None
        summary = " ".join(content.split()).strip().strip('"')
        if not summary:
            return None
        return summary[:220]

    def _evaluate_with_proxy(self, payload: ModerationEvaluationInput) -> ModerationDecision | None:
        request = Request(
            url=f"{self.base_url}/api/moderation/evaluate",
            data=json.dumps(_payload_to_json(payload), ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "WarlordsModerationBot/1.0",
                "Authorization": f"Bearer {self.shared_token}",
            },
            method="POST",
        )
        raw = _perform_request(request, timeout_seconds=self.timeout_seconds)
        if raw is None:
            return None
        try:
            return _decision_from_json(json.loads(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def _evaluate_with_deepseek(self, payload: ModerationEvaluationInput) -> ModerationDecision | None:
        content = self._deepseek_json_completion(
            messages=_build_moderation_messages(payload),
            temperature=0.16,
            max_tokens=280,
        )
        if content is None:
            return None

        decision = _decision_from_json(content)
        if not decision.source or decision.source == "ai":
            return ModerationDecision(
                decision=decision.decision,
                confidence=decision.confidence,
                reason=decision.reason,
                labels=decision.labels,
                timeout_minutes=decision.timeout_minutes,
                reply_text=decision.reply_text,
                source=f"deepseek:{self.model}",
                requires_admin_alert=decision.requires_admin_alert,
                should_delete_message=decision.should_delete_message,
                should_timeout_user=decision.should_timeout_user,
                reaction_emoji=decision.reaction_emoji,
            )
        return decision

    def _request_persona_response(
        self,
        *,
        payload: ModerationEvaluationInput,
        previous_user_content: str,
        previous_bot_reply: str,
        recent_channel_replies: tuple[str, ...],
        force_reply: bool,
    ) -> PersonaResponse | None:
        messages = _build_persona_messages(
            payload,
            previous_user_content=previous_user_content,
            previous_bot_reply=previous_bot_reply,
            recent_channel_replies=recent_channel_replies,
        )
        if force_reply:
            messages.append(
                {
                    "role": "user",
                    "content": "К тебе обратились напрямую. Не молчи без причины: верни короткий reply_text или уместную reaction_emoji.",
                }
            )

        data = self._deepseek_json_completion(
            messages=messages,
            temperature=0.78 if force_reply else 0.72,
            max_tokens=190,
        )
        if data is None:
            return None

        reply = _sanitize_persona_reply(" ".join(str(data.get("reply_text", "")).split()).strip().strip('"'))
        reaction_emoji = _normalize_reaction_emoji(str(data.get("reaction_emoji", "")))
        if not reply and not reaction_emoji:
            return None
        return PersonaResponse(reply_text=reply[:220], reaction_emoji=reaction_emoji)

    def _request_persona_plain_reply(
        self,
        *,
        payload: ModerationEvaluationInput,
        previous_user_content: str,
        previous_bot_reply: str,
        recent_channel_replies: tuple[str, ...],
    ) -> str:
        messages = _build_persona_messages(
            payload,
            previous_user_content=previous_user_content,
            previous_bot_reply=previous_bot_reply,
            recent_channel_replies=recent_channel_replies,
        )
        messages.append(
            {
                "role": "user",
                "content": (
                    "Ответь одной живой репликой обычным текстом, без JSON и без лекций про ограничения. "
                    "Если к тебе обратились с вопросом или репликой, лучше ответить, чем молчать."
                ),
            }
        )

        content = self._deepseek_chat_completion(
            {
                "model": self.model,
                "temperature": 0.78,
                "max_tokens": 220,
                "messages": messages,
            }
        )
        if not content:
            return ""

        normalized = content.strip()
        if normalized.startswith("{"):
            try:
                data = _parse_json_object(normalized)
            except (ValueError, json.JSONDecodeError):
                pass
            else:
                normalized = str(data.get("reply_text", "")).strip()

        return _sanitize_persona_reply(" ".join(normalized.split()).strip().strip('"'))[:260]

    def _deepseek_json_completion(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any] | None:
        content = self._deepseek_chat_completion(
            {
                "model": self.model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": messages,
            }
        )
        if not content:
            return None
        try:
            return _parse_json_object(content)
        except (ValueError, json.JSONDecodeError):
            return None

    def _deepseek_chat_completion(self, body: dict[str, Any]) -> str | None:
        request = Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "WarlordsDeepSeekClient/1.0",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        raw = _perform_request(request, timeout_seconds=self.timeout_seconds)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            return None


def _perform_request(request: Request, *, timeout_seconds: int) -> str | None:
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None


def _payload_to_json(payload: ModerationEvaluationInput) -> dict[str, Any]:
    result = asdict(payload)
    result["recent_messages"] = [asdict(item) for item in payload.recent_messages]
    return result


def _decision_from_json(data: dict[str, Any]) -> ModerationDecision:
    decision = str(data.get("decision", "allow")).strip().lower()
    labels = tuple(str(item).strip() for item in data.get("labels", []) if str(item).strip())
    return ModerationDecision(
        decision=decision,
        confidence=float(data.get("confidence", 0.0)),
        reason=str(data.get("reason", "")).strip(),
        labels=labels,
        timeout_minutes=max(0, int(data.get("timeout_minutes", 0))),
        reply_text=str(data.get("reply_text", "")).strip(),
        source=str(data.get("source", "ai")).strip() or "ai",
        requires_admin_alert=bool(data.get("requires_admin_alert", decision == "scam_alert")),
        should_delete_message=bool(data.get("should_delete_message", decision in {"light_violation", "ban_violation"})),
        should_timeout_user=bool(data.get("should_timeout_user", decision == "light_violation")),
        reaction_emoji=_normalize_reaction_emoji(str(data.get("reaction_emoji", ""))),
    )


def _build_moderation_messages(payload: ModerationEvaluationInput) -> list[dict[str, str]]:
    return build_moderation_messages(payload)


def _build_persona_messages(
    payload: ModerationEvaluationInput,
    *,
    previous_user_content: str,
    previous_bot_reply: str,
    recent_channel_replies: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    return build_persona_messages(
        payload,
        previous_user_content=previous_user_content,
        previous_bot_reply=previous_bot_reply,
        recent_channel_replies=recent_channel_replies,
    )


def _parse_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if not candidate:
        raise ValueError("Empty response.")
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("JSON object not found.")
        candidate = candidate[start : end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("JSON response must be an object.")
    return parsed


def _normalize_reaction_emoji(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return ""
    return normalized[:32]


_PERSONA_REPLY_PATTERNS = (
    re.compile(r"(?:[,.\s-])*если\s+нужна\s+помощь[^\n.!?]*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"(?:[,.\s-])*если\s+что-то\s+по\s+серверу[^\n.!?]*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"(?:[,.\s-])*(?:но\s+)?я\s+больше\s+по[^\n.!?]*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"(?:[,.\s-])*это\s+уже\s+не\s+моя\s+компетенция[^\n.!?]*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"(?:[,.\s-])*я\s+не\s+в\s+курсе\s+деталей[^\n.!?]*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"(?:[,.\s-])*модерация\s+разбер[её]тся[^\n.!?]*[.!?]?\s*$", re.IGNORECASE),
    re.compile(r"(?:[,.\s-])*(?:[А-ЯЁA-Z][^.!?]{0,80})?ты\s+же\s+лучше\s+меня[^\n.!?]*[.!?]?\s*$", re.IGNORECASE),
)


def _sanitize_persona_reply(reply: str) -> str:
    cleaned = " ".join(reply.split()).strip().strip('"')
    if not cleaned:
        return ""
    for pattern in _PERSONA_REPLY_PATTERNS:
        cleaned = pattern.sub("", cleaned).strip(" ,.-")
    return cleaned[:220]


_PERSONA_MENTION_RE = re.compile(r"<@!?\d+>|<@&\d+>")
_DIRECT_GREETING_RE = re.compile(
    r"^(?:ну\s+)?(?:ку|привет|здарова|здорово|хай|йо|hello|hi)\b[!.,?\s-]*$",
    re.IGNORECASE,
)


def _normalize_direct_address_text(text: str) -> str:
    stripped = _PERSONA_MENTION_RE.sub(" ", text or "")
    return " ".join(stripped.split()).strip()


def _build_direct_greeting_fallback(text: str) -> PersonaResponse | None:
    normalized = _normalize_direct_address_text(text).casefold()
    if not normalized or not _DIRECT_GREETING_RE.match(normalized):
        return None

    if normalized.startswith("ку"):
        return PersonaResponse(reply_text="Ку.", reaction_emoji="")
    if normalized.startswith(("здарова", "здорово")):
        return PersonaResponse(reply_text="Здарова.", reaction_emoji="")
    if normalized.startswith(("hello", "hi")):
        return PersonaResponse(reply_text="Привет.", reaction_emoji="")
    return PersonaResponse(reply_text="Привет.", reaction_emoji="")
