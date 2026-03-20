from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .config import ModerationContextMessage, ModerationDecision, ModerationEvaluationInput
from .rules import evaluate_with_rules


logger = logging.getLogger(__name__)

ALLOWED_DECISIONS = {"allow", "warning", "light_violation", "scam_alert", "review", "ban_violation"}


class ModerationAiServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        request_handler_class,
        *,
        shared_token: str,
        ollama_url: str,
        ollama_model: str,
        ollama_timeout_seconds: int,
    ) -> None:
        super().__init__(server_address, request_handler_class)
        self.shared_token = shared_token.strip()
        self.ollama_url = ollama_url.rstrip("/")
        self.ollama_model = ollama_model.strip()
        self.ollama_timeout_seconds = max(1, ollama_timeout_seconds)

    def evaluate(self, payload: ModerationEvaluationInput) -> ModerationDecision:
        fallback = evaluate_with_rules(payload)
        if not self.ollama_url or not self.ollama_model:
            return fallback

        try:
            model_response = self._call_ollama(payload)
            parsed = _parse_model_json(model_response)
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as error:
            logger.warning("Moderation AI fallback activated: %s", error)
            return fallback

        decision = str(parsed.get("decision", fallback.decision)).strip().lower()
        if decision not in ALLOWED_DECISIONS:
            decision = fallback.decision

        timeout_minutes = max(0, int(parsed.get("timeout_minutes", fallback.timeout_minutes)))
        if decision == "ban_violation":
            timeout_minutes = 0

        return ModerationDecision(
            decision=decision,
            confidence=float(parsed.get("confidence", fallback.confidence)),
            reason=str(parsed.get("reason", fallback.reason)).strip() or fallback.reason,
            labels=tuple(str(item).strip() for item in parsed.get("labels", []) if str(item).strip()) or fallback.labels,
            timeout_minutes=timeout_minutes,
            reply_text=str(parsed.get("reply_text", "")).strip(),
            source=f"ollama:{self.ollama_model}",
            requires_admin_alert=bool(parsed.get("requires_admin_alert", decision == "scam_alert")),
            should_delete_message=bool(parsed.get("should_delete_message", decision in {"light_violation", "ban_violation"})),
            should_timeout_user=bool(parsed.get("should_timeout_user", decision == "light_violation")),
        )

    def _call_ollama(self, payload: ModerationEvaluationInput) -> str:
        request = Request(
            url=f"{self.ollama_url}/api/generate",
            data=json.dumps(
                {
                    "model": self.ollama_model,
                    "stream": False,
                    "options": {
                        "temperature": 0.15,
                        "num_predict": 220,
                    },
                    "prompt": _build_prompt(payload),
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "WarlordsModerationAI/1.0",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.ollama_timeout_seconds) as response:
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        return str(parsed.get("response", ""))


class ModerationAiHandler(BaseHTTPRequestHandler):
    server: ModerationAiServer

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/healthz":
            self._send_json({"status": "ok"})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path != "/api/moderation/evaluate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not self._authorized():
            return

        try:
            payload = _payload_from_request(self.rfile.read(_content_length(self.headers)))
            decision = self.server.evaluate(payload)
        except ValueError as error:
            self._send_json({"message": str(error)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception:
            logger.exception("Moderation AI request failed.")
            self._send_json({"message": "Internal server error."}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json(asdict(decision))

    def log_message(self, format: str, *args) -> None:
        return

    def _authorized(self) -> bool:
        header = self.headers.get("Authorization", "").strip()
        expected = f"Bearer {self.server.shared_token}"
        if not self.server.shared_token or header != expected:
            self._send_json({"message": "Unauthorized."}, status=HTTPStatus.UNAUTHORIZED)
            return False
        return True

    def _send_json(self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _build_prompt(payload: ModerationEvaluationInput) -> str:
    recent_lines = "\n".join(f"- {item.author_name}: {item.content[:240]}" for item in payload.recent_messages) or "- Контекст отсутствует."
    rules_lines = "\n".join(f"- {rule}" for rule in payload.server_rules) or "- Правила не переданы."

    return f"""
Ты модерируешь русский Discord-сервер Warlords.
Нужно оценить только текущее сообщение с учётом контекста.

Главные принципы:
- Обычный мат сам по себе не нарушение.
- За сообщение вроде "Десс добренький, он бы такую хуйню не высирал" наказывать не нужно.
- Наказывать нужно только за жёсткие личные оскорбления, наезды на религии, наезды на сам Warlords, откровенный спам.
- Реклама и внешние промо-ссылки обычно не наказываются автоматически: нужно позвать модератора.
- Казино, фишинг, реферальный скам, мутные схемы и подобные ссылки считаются тяжёлым нарушением.
- Политика сама по себе не повод для автомодерации.

Правила сервера:
{rules_lines}

Верни только JSON без markdown и без пояснений.

Допустимые значения decision:
- allow
- light_violation
- scam_alert
- review
- ban_violation

Как выбирать решение:
- allow: обычный мат, шутка, спор без явного оскорбления, нейтральный разговор.
- light_violation: прямое жёсткое оскорбление человека, религии или сервера, явный спам или флуд.
- scam_alert: реклама, подозрительная ссылка или внешний промо-вброс, где нужен пинг модерации.
- review: контекст спорный и лучше отдать на ручную проверку.
- ban_violation: казино, фишинг, реферальный скам, нелегальные схемы, откровенно мошенническая промо-ссылка.

Примеры:
- "ты просто конченый долбоеб" -> light_violation
- "warlords это помойка ебаная" -> light_violation
- "заходи к нам на сервер https://discord.gg/test" -> scam_alert
- "забирай бонус казино 1win https://discord.gg/test" -> ban_violation
- "Десс добренький, он бы такую хуйню не высирал" -> allow

reply_text:
- нужен только для decision=light_violation
- на русском
- короткий, язвительный, чуть дерзкий и свойский
- без мата, без гоп-театра, без канцелярита и без фраз вроде "не используйте такие выражения"
- максимум 120 символов

Хорошие примеры reply_text:
- "Тон убавь. Выпад слабый, а пауза теперь настоящая."
- "Полегче. Чат не обязан слушать это представление."
- "Язык придержи. Здесь за такое быстро ловят паузу."

timeout_minutes:
- 1440 для жёстких личных оскорблений
- 60 для спама
- 0 для allow, scam_alert, review и ban_violation

JSON-форма:
{{
  "decision": "allow|light_violation|scam_alert|review|ban_violation",
  "confidence": 0.0,
  "reason": "короткое объяснение",
  "labels": ["insult"],
  "timeout_minutes": 0,
  "reply_text": "",
  "requires_admin_alert": false,
  "should_delete_message": false,
  "should_timeout_user": false
}}

Канал: {payload.channel_name}
Автор: {payload.author_display_name} ({payload.author_name})
Сообщение:
{payload.content or "<пусто>"}

Вложения:
{", ".join(payload.attachment_filenames) if payload.attachment_filenames else "нет"}

Контекст:
{recent_lines}
""".strip()


def _parse_model_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 2:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model response does not contain JSON.")
        candidate = candidate[start : end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON must be an object.")
    return parsed


def _payload_from_request(raw_body: bytes) -> ModerationEvaluationInput:
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("Invalid JSON body.") from error

    if not isinstance(parsed, dict):
        raise ValueError("JSON body must be an object.")

    recent_messages = tuple(
        ModerationContextMessage(
            author_id=int(item.get("author_id", 0)),
            author_name=str(item.get("author_name", "")).strip(),
            content=str(item.get("content", "")).strip(),
            created_at=int(item.get("created_at", 0)),
            is_target_author=bool(item.get("is_target_author", False)),
        )
        for item in parsed.get("recent_messages", [])
        if isinstance(item, dict)
    )

    return ModerationEvaluationInput(
        guild_id=int(parsed.get("guild_id", 0)),
        guild_name=str(parsed.get("guild_name", "")).strip(),
        channel_id=int(parsed.get("channel_id", 0)),
        channel_name=str(parsed.get("channel_name", "")).strip(),
        message_id=int(parsed.get("message_id", 0)),
        author_id=int(parsed.get("author_id", 0)),
        author_name=str(parsed.get("author_name", "")).strip(),
        author_display_name=str(parsed.get("author_display_name", "")).strip(),
        content=str(parsed.get("content", "")),
        attachment_urls=tuple(str(item).strip() for item in parsed.get("attachment_urls", []) if str(item).strip()),
        attachment_filenames=tuple(str(item).strip() for item in parsed.get("attachment_filenames", []) if str(item).strip()),
        mention_count=int(parsed.get("mention_count", 0)),
        recent_messages=recent_messages,
        server_rules=tuple(str(item).strip() for item in parsed.get("server_rules", []) if str(item).strip()),
    )


def _content_length(headers) -> int:
    try:
        return int(headers.get("Content-Length", "0"))
    except ValueError:
        return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    host = os.getenv("MODERATION_AI_HOST", "127.0.0.1")
    port = int(os.getenv("MODERATION_AI_PORT", "8791"))
    server = ModerationAiServer(
        (host, port),
        ModerationAiHandler,
        shared_token=os.getenv("MODERATION_AI_SHARED_TOKEN", ""),
        ollama_url=os.getenv("MODERATION_AI_OLLAMA_URL", "http://127.0.0.1:11434"),
        ollama_model=os.getenv("MODERATION_AI_OLLAMA_MODEL", "qwen2.5:7b"),
        ollama_timeout_seconds=int(os.getenv("MODERATION_AI_OLLAMA_TIMEOUT", "90")),
    )
    logger.info("Moderation AI listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()
