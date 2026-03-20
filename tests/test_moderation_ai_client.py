from __future__ import annotations

import unittest

from tests import support  # noqa: F401
from modules.moderation.ai_client import (
    _build_direct_greeting_fallback,
    _build_moderation_messages,
    _build_persona_messages,
    _decision_from_json,
    _parse_json_object,
    _sanitize_persona_reply,
)
from modules.moderation.config import ModerationContextMessage, ModerationEvaluationInput, ModerationHistorySnapshot


class ModerationAiClientTests(unittest.TestCase):
    def _payload(self) -> ModerationEvaluationInput:
        return ModerationEvaluationInput(
            guild_id=1,
            guild_name="Warlords",
            channel_id=2,
            channel_name="chat",
            message_id=3,
            author_id=4,
            author_name="user",
            author_display_name="User",
            content="что ты умеешь?",
            attachment_filenames=("proof.png",),
            attachment_ocr_texts=("1win bonus withdraw success",),
            recent_messages=(
                ModerationContextMessage(
                    author_id=4,
                    author_name="User",
                    content="привет",
                    created_at=1,
                    is_target_author=True,
                ),
            ),
            server_rules=("Обычный мат без личного наезда автомод не трогает.",),
            server_facts=("Информация о сервере находится в канале <#1343124803858599977>.",),
            reply_to_bot=True,
            bot_mentioned=False,
            addressed_to_bot=True,
            author_is_protected=False,
            author_role_names=("Admin", "Dev"),
            author_known_profile="messire (mss1r, мессир) - создатель и разработчик бота",
            author_observed_character="Обычно пишет коротко и по делу.",
            author_recent_samples=("что по открытию", "ну привет", "когда запуск", "где тикеты"),
            author_history=ModerationHistorySnapshot(
                warning_count_24h=1,
                warning_count_72h=1,
                light_violation_count_72h=0,
                ban_violation_count_30d=0,
                last_decision="warning",
                last_reason="резковато ответил",
                last_labels=("disrespect",),
                last_timeout_minutes=0,
                last_event_age_minutes=45,
                last_warning_age_minutes=45,
                last_sanction_age_minutes=-1,
                recent_events=("45м назад: warning [disrespect] — резковато ответил",),
            ),
            known_people_directory=("Jamb1 (Джамби) -> <@557814715913469976> - создатель сервера",),
            observed_people_directory=(
                "Cosmo Lord -> <@847841141655076864> - Задаёт ироничные вопросы ботам с условными ответами.",
            ),
            target_subject_hint="Cosmo Lord (@cosmo_lord) -> <@847841141655076864> - Задаёт ироничные вопросы ботам с условными ответами.",
            guild_staff_directory=(
                "messire -> <@1034533546863382649> - владелец сервера; роли: Администратор, Разработчик",
                "Tigran -> <@710800410587299872> - модератор; роли: Moderator",
            ),
            guild_channel_directory=(
                "#info -> <#1343124803858599977>",
                "#tickets -> <#1426228872105693306>",
            ),
            guild_role_directory=("Администратор", "Moderator", "Player"),
        )

    def test_parse_json_object_extracts_embedded_json(self) -> None:
        parsed = _parse_json_object('text {"decision":"allow"} text')

        self.assertEqual(parsed["decision"], "allow")

    def test_sanitize_persona_reply_strips_server_help_tail(self) -> None:
        reply = _sanitize_persona_reply("Я тебя услышал. Если нужна помощь по серверу — спрашивай.")

        self.assertEqual(reply, "Я тебя услышал")

    def test_sanitize_persona_reply_strips_stock_competence_tail(self) -> None:
        reply = _sanitize_persona_reply("Великая Алмасия? Похоже на старый лор. Но я больше по текущему проекту.")

        self.assertEqual(reply, "Великая Алмасия? Похоже на старый лор")

    def test_decision_from_json_builds_moderation_decision(self) -> None:
        decision = _decision_from_json(
            {
                "decision": "light_violation",
                "confidence": 0.91,
                "reason": "Оскорбление",
                "labels": ["insult"],
                "timeout_minutes": 1440,
                "reply_text": "Полегче.",
                "reaction_emoji": "🤨",
            }
        )

        self.assertEqual(decision.decision, "light_violation")
        self.assertEqual(decision.timeout_minutes, 1440)
        self.assertEqual(decision.reply_text, "Полегче.")
        self.assertEqual(decision.reaction_emoji, "🤨")

    def test_build_persona_messages_include_live_directories_and_guidance(self) -> None:
        messages = _build_persona_messages(
            self._payload(),
            previous_user_content="сервер завтра в три?",
            previous_bot_reply="Завтра в три.",
        )

        system_prompt = messages[0]["content"]
        user_prompt = messages[1]["content"]

        self.assertIn("Живая администрация сервера", system_prompt)
        self.assertIn("<@1034533546863382649>", system_prompt)
        self.assertIn("#info -> <#1343124803858599977>", system_prompt)
        self.assertIn("Наблюдения по участникам текущего разговора", system_prompt)
        self.assertIn("<@847841141655076864>", system_prompt)
        self.assertIn("Шутку про «завтра в 3» используй только", system_prompt)
        self.assertIn("сначала трактуй незнакомые названия как местный контекст", system_prompt)
        self.assertIn("Если вопрос выглядит как общий вопрос о мире, истории, астрономии", system_prompt)
        self.assertIn("Не перекладывай ответ на собеседника", system_prompt)
        self.assertIn("Ты сам модерируешь чат", system_prompt)
        self.assertIn("Не подменяй список известных людей списком админов", system_prompt)
        self.assertIn("Если спрашивают «кто это такой»", system_prompt)
        self.assertIn("не размывай всё до «обычный участник»", system_prompt)
        self.assertIn("не обязан отвечать текстом", system_prompt)
        self.assertIn("Если реплика реально двигает разговор дальше", system_prompt)
        self.assertIn("1-3 коротких фраз", system_prompt)
        self.assertIn('"reaction_emoji": ""', user_prompt)
        self.assertIn("Вероятный предмет вопроса:\nCosmo Lord (@cosmo_lord)", user_prompt)
        self.assertIn("сервер завтра в три?", user_prompt)
        self.assertIn("Завтра в три.", user_prompt)
        self.assertIn("Admin, Dev", user_prompt)
        self.assertIn("- addressed_to_bot: true", user_prompt)

    def test_build_persona_messages_strip_raw_discord_mentions_from_messages(self) -> None:
        payload = self._payload()
        payload.content = "<@&1482033675368665182> ку"

        messages = _build_persona_messages(
            payload,
            previous_user_content="<@&1482033675368665182> привет",
            previous_bot_reply="Ку.",
        )

        user_prompt = messages[1]["content"]

        self.assertIn("Текущее сообщение:\nку", user_prompt)
        self.assertIn("Предыдущая реплика пользователя:\nпривет", user_prompt)

    def test_build_moderation_messages_are_ai_first_and_contextual(self) -> None:
        messages = _build_moderation_messages(self._payload())
        system_prompt = messages[0]["content"]
        user_prompt = messages[1]["content"]

        self.assertIn("Обычный мат, подколы и шум вокруг бота сами по себе не нарушение", system_prompt)
        self.assertIn("Если один и тот же автор пишет короткие куски подряд", system_prompt)
        self.assertIn("При light_violation и ban_violation обычно возвращай короткий reply_text", system_prompt)
        self.assertIn("1win bonus withdraw success", user_prompt)
        self.assertIn("что ты умеешь?", user_prompt)
        self.assertIn("Недавняя история модерации автора", user_prompt)
        self.assertIn("warning за 24ч: 1", user_prompt)
        self.assertIn('"decision": "allow|warning|light_violation|scam_alert|review|ban_violation"', user_prompt)

    def test_direct_greeting_fallback_handles_role_mention_greeting(self) -> None:
        response = _build_direct_greeting_fallback("<@&1482033675368665182> ку")

        self.assertIsNotNone(response)
        assert response is not None
        self.assertEqual(response.reply_text, "Ку.")


if __name__ == "__main__":
    unittest.main()
