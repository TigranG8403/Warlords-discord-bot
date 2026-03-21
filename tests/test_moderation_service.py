from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests import support  # noqa: F401
from modules.moderation.config import ModerationDecision, ModerationEvaluationInput, ModerationEventRecord, ModerationRuntimeConfig
from modules.moderation.repository import ModerationRepository
from modules.moderation.service import (
    ModerationService,
    _build_observed_people_directory,
    _build_target_subject_hint,
    _enrich_reply_mentions,
)


class _FakeAiClient:
    def __init__(self, decision: ModerationDecision | None) -> None:
        self._decision = decision

    def is_configured(self) -> bool:
        return True

    def evaluate(self, _payload: ModerationEvaluationInput) -> ModerationDecision | None:
        return self._decision


class _FakeAttachment:
    def __init__(self, filename: str) -> None:
        self.filename = filename


class _FakeMessage:
    def __init__(
        self,
        *,
        content: str,
        attachments: tuple[_FakeAttachment, ...] = (),
        mentions: tuple[object, ...] = (),
    ) -> None:
        self.content = content
        self.attachments = attachments
        self.mentions = mentions


class ModerationServiceTests(unittest.TestCase):
    def _service(self, decision: ModerationDecision | None) -> ModerationService:
        return ModerationService(
            ModerationRepository(Path(tempfile.mkdtemp()) / "moderation.sqlite3"),
            ai_client=_FakeAiClient(decision) if decision is not None else None,
            runtime_config=ModerationRuntimeConfig(confidence_threshold=0.78),
        )

    def _payload(self, **overrides: object) -> ModerationEvaluationInput:
        base = dict(
            guild_id=1,
            guild_name="Warlords",
            channel_id=2,
            channel_name="chat",
            message_id=3,
            author_id=77,
            author_name="user",
            author_display_name="User",
            content="сомнительный текст",
        )
        base.update(overrides)
        return ModerationEvaluationInput(**base)

    def test_addressed_to_bot_messages_are_always_considered_with_ai_enabled(self) -> None:
        service = self._service(
            ModerationDecision(
                decision="allow",
                confidence=0.7,
                reason="Обычный вопрос к боту.",
                source="deepseek:deepseek-chat",
            )
        )

        message = _FakeMessage(content="Почему ты копируешь прошлые фразы, как полуумный")

        self.assertTrue(service.should_consider(message, addressed_to_bot=True))

    def test_light_violation_keeps_ai_reply_and_operational_policy(self) -> None:
        service = self._service(
            ModerationDecision(
                decision="light_violation",
                confidence=0.95,
                reason="Явное оскорбление",
                labels=("insult",),
                timeout_minutes=60,
                reply_text="Полегче с языком.",
                source="deepseek:deepseek-chat",
                should_delete_message=False,
                should_timeout_user=False,
            )
        )

        result = service.evaluate(self._payload(content="иди нахуй, долбоеб"))

        self.assertEqual(result.decision, "light_violation")
        self.assertEqual(result.timeout_minutes, 60)
        self.assertTrue(result.should_delete_message)
        self.assertTrue(result.should_timeout_user)
        self.assertEqual(result.reply_text, "Полегче с языком.")

    def test_first_warning_stays_warning(self) -> None:
        service = self._service(
            ModerationDecision(
                decision="warning",
                confidence=0.82,
                reason="Резкий подкол без нужды.",
                labels=("disrespect",),
                reply_text="Полегче.",
                source="deepseek:deepseek-chat",
            )
        )

        result = service.evaluate(self._payload(content="ну ты и душный"))

        self.assertEqual(result.decision, "warning")
        self.assertEqual(result.timeout_minutes, 0)
        self.assertFalse(result.should_delete_message)
        self.assertFalse(result.should_timeout_user)
        self.assertEqual(result.reply_text, "Полегче.")

    def test_repeated_warning_escalates_to_timeout(self) -> None:
        repository = ModerationRepository(Path(tempfile.mkdtemp()) / "moderation.sqlite3")
        repository.add_event(
            ModerationEventRecord(
                guild_id=1,
                channel_id=2,
                message_id=41,
                author_id=77,
                author_name="user",
                message_content="первый перегиб",
                decision="warning",
                reason="Грубовато.",
                labels=("disrespect",),
                timeout_minutes=0,
                source="deepseek:deepseek-chat",
                confidence=0.8,
            )
        )
        service = ModerationService(
            repository,
            ai_client=_FakeAiClient(
                ModerationDecision(
                    decision="warning",
                    confidence=0.85,
                    reason="Снова перегибает.",
                    labels=("disrespect",),
                    reply_text="Я уже предупреждал.",
                    source="deepseek:deepseek-chat",
                )
            ),
            runtime_config=ModerationRuntimeConfig(confidence_threshold=0.78),
        )

        result = service.evaluate(
            self._payload(
                content="ну и че",
                author_id=77,
                author_history=repository.get_user_history_snapshot(guild_id=1, user_id=77),
            )
        )

        self.assertEqual(result.decision, "light_violation")
        self.assertEqual(result.timeout_minutes, 90)
        self.assertTrue(result.should_delete_message)
        self.assertTrue(result.should_timeout_user)
        self.assertIn("warning_escalation", result.labels)

    def test_recent_warnings_raise_minimum_timeout(self) -> None:
        repository = ModerationRepository(Path(tempfile.mkdtemp()) / "moderation.sqlite3")
        repository.add_event(
            ModerationEventRecord(
                guild_id=1,
                channel_id=2,
                message_id=51,
                author_id=77,
                author_name="user",
                message_content="предупреждение раз",
                decision="warning",
                reason="Грубовато.",
                labels=("disrespect",),
                timeout_minutes=0,
                source="deepseek:deepseek-chat",
                confidence=0.8,
            )
        )
        repository.add_event(
            ModerationEventRecord(
                guild_id=1,
                channel_id=2,
                message_id=52,
                author_id=77,
                author_name="user",
                message_content="предупреждение два",
                decision="warning",
                reason="Опять грубовато.",
                labels=("disrespect",),
                timeout_minutes=0,
                source="deepseek:deepseek-chat",
                confidence=0.8,
            )
        )
        service = ModerationService(
            repository,
            ai_client=_FakeAiClient(
                ModerationDecision(
                    decision="light_violation",
                    confidence=0.9,
                    reason="Перешел грань.",
                    labels=("insult",),
                    timeout_minutes=30,
                    reply_text="Отдохни.",
                    source="deepseek:deepseek-chat",
                )
            ),
            runtime_config=ModerationRuntimeConfig(confidence_threshold=0.78),
        )

        result = service.evaluate(
            self._payload(
                content="ты уже задрал",
                author_id=77,
                author_history=repository.get_user_history_snapshot(guild_id=1, user_id=77),
            )
        )

        self.assertEqual(result.decision, "light_violation")
        self.assertEqual(result.timeout_minutes, 90)

    def test_low_signal_review_is_softened_to_allow(self) -> None:
        service = self._service(
            ModerationDecision(
                decision="review",
                confidence=0.5,
                reason="Смысл не очень ясен.",
                source="deepseek:deepseek-chat",
            )
        )

        result = service.evaluate(self._payload(content="пупу"))

        self.assertEqual(result.decision, "allow")

    def test_review_with_labels_is_kept(self) -> None:
        service = self._service(
            ModerationDecision(
                decision="review",
                confidence=0.62,
                reason="Случай спорный, нужен живой взгляд.",
                labels=("insult",),
                reply_text="Случай мутный. Пусть это лучше посмотрят руками.",
                reaction_emoji="🤨",
                source="deepseek:deepseek-chat",
            )
        )

        result = service.evaluate(self._payload())

        self.assertEqual(result.decision, "review")
        self.assertEqual(result.reply_text, "Случай мутный. Пусть это лучше посмотрят руками.")
        self.assertEqual(result.reaction_emoji, "🤨")

    def test_falls_back_to_rules_when_ai_is_missing(self) -> None:
        service = self._service(None)

        result = service.evaluate(self._payload(content="ты просто конченый долбоеб"))

        self.assertEqual(result.decision, "light_violation")
        self.assertTrue(result.should_delete_message)
        self.assertTrue(result.should_timeout_user)

    def test_direct_bot_greeting_enters_ai_moderation_path(self) -> None:
        service = self._service(
            ModerationDecision(
                decision="allow",
                confidence=0.6,
                reason="Даже не должно вызываться на обычном приветствии.",
                source="deepseek:deepseek-chat",
            )
        )

        result = service.should_consider(_FakeMessage(content="@Warlords ку"), addressed_to_bot=True)

        self.assertTrue(result)

    def test_direct_bot_insult_still_enters_moderation_path(self) -> None:
        service = self._service(
            ModerationDecision(
                decision="allow",
                confidence=0.8,
                reason="Не должно ломать вход в модерацию.",
                source="deepseek:deepseek-chat",
            )
        )

        result = service.should_consider(_FakeMessage(content="@Warlords ты долбоеб"), addressed_to_bot=True)

        self.assertTrue(result)

    def test_direct_bot_message_with_image_still_enters_moderation_path(self) -> None:
        service = self._service(
            ModerationDecision(
                decision="allow",
                confidence=0.8,
                reason="Не должно обходить OCR-путь.",
                source="deepseek:deepseek-chat",
            )
        )
        service.ocr_service = SimpleNamespace(should_scan_attachment=lambda attachment: attachment.filename.endswith(".png"))

        result = service.should_consider(
            _FakeMessage(content="@Warlords глянь", attachments=(_FakeAttachment("example.png"),)),
            addressed_to_bot=True,
        )

        self.assertTrue(result)

    def test_rules_override_ai_allow_for_obvious_ocr_scam(self) -> None:
        service = self._service(
            ModerationDecision(
                decision="allow",
                confidence=0.82,
                reason="Нарушений не вижу",
                source="deepseek:deepseek-chat",
            )
        )

        result = service.evaluate(
            self._payload(
                content="bro",
                attachment_filenames=("img.png",),
                attachment_ocr_texts=(
                    "claim your reward go to cenatwin.com enter the promo code receive your $2500 bonus withdraw instantly "
                    "[ocr_hints: brand_cenatwin, bonus, withdraw, promo_code, claim_reward, register, money_amount, suspicious_domain]",
                ),
            )
        )

        self.assertEqual(result.decision, "ban_violation")
        self.assertIn("ocr", result.labels)
        self.assertTrue(result.should_delete_message)

    def test_ai_semantic_allow_is_not_overridden_by_fallback_rules(self) -> None:
        service = self._service(
            ModerationDecision(
                decision="allow",
                confidence=0.86,
                reason="Контекст не тянет на нарушение",
                source="deepseek:deepseek-chat",
            )
        )

        result = service.evaluate(self._payload(content="этот сервер говно"))

        self.assertEqual(result.decision, "allow")

    def test_protected_reply_downgrades_sanction_without_extra_template(self) -> None:
        service = self._service(None)

        result = service.build_protected_reply_decision(
            author_id=777,
            display_name="Admin",
            decision=ModerationDecision(
                decision="light_violation",
                confidence=0.95,
                reason="Есть прямое жёсткое оскорбление человека.",
                labels=("insult",),
                timeout_minutes=1440,
                reply_text="Полегче с тоном.",
                source="deepseek:deepseek-chat",
                should_delete_message=True,
                should_timeout_user=True,
            ),
        )

        self.assertEqual(result.decision, "review")
        self.assertIn("выше бота по роли", result.reason)
        self.assertIn("protected_member", result.labels)
        self.assertEqual(result.reply_text, "Полегче с тоном.")

    def test_archive_search_text_contains_mention_nick_and_tag(self) -> None:
        service = self._service(None)

        result = service._build_archive_search_text(
            self._payload(
                author_id=555,
                author_name="cosmo_lord",
                author_display_name="Cosmo Lord",
                content="тест",
            )
        )

        self.assertIn("<@555>", result)
        self.assertIn("Cosmo Lord", result)
        self.assertIn("@cosmo_lord", result)

    def test_compact_archive_search_text_is_less_noisy(self) -> None:
        service = self._service(None)

        result = service._build_compact_archive_search_text(
            self._payload(
                author_id=555,
                author_name="cosmo_lord",
                author_display_name="Cosmo Lord",
                content="тест",
            )
        )

        self.assertTrue(result.startswith("-# search:"))
        self.assertIn("<@555>", result)
        self.assertIn("Cosmo Lord", result)
        self.assertIn("@cosmo_lord", result)

    def test_enrich_reply_mentions_links_known_channels(self) -> None:
        repository = ModerationRepository(Path(tempfile.mkdtemp()) / "moderation.sqlite3")
        guild = SimpleNamespace(
            channels=(
                SimpleNamespace(id=10, name="⌠⌡админ-чат"),
                SimpleNamespace(id=11, name="правила"),
            ),
            members=(),
        )

        result = _enrich_reply_mentions(
            guild,
            "Ты же только что спрашивал. В #⌠⌡админ-чат. Потом загляни в #правила.",
            repository,
        )

        self.assertIn("<#10>", result)
        self.assertIn("<#11>", result)

    def test_build_observed_people_directory_uses_recent_participants(self) -> None:
        repository = ModerationRepository(Path(tempfile.mkdtemp()) / "moderation.sqlite3")
        repository.record_user_observation(
            guild_id=1,
            user_id=847841141655076864,
            author_name="Cosmo Lord",
            role_names=("Участник",),
            content="Алмасия — это страна захватившая африку",
            decision="allow",
            addressed_to_bot=False,
            labels=(),
        )
        repository.save_user_character_summary(
            guild_id=1,
            user_id=847841141655076864,
            summary="Задаёт ироничные вопросы ботам с условными ответами.",
        )

        guild = SimpleNamespace(
            id=1,
            members=(
                SimpleNamespace(id=847841141655076864, display_name="Cosmo Lord", roles=(SimpleNamespace(name="Участник"),)),
            ),
        )
        message = SimpleNamespace(
            author=SimpleNamespace(id=77),
            mentions=(),
        )
        recent_messages = [
            SimpleNamespace(author_id=847841141655076864),
        ]

        result = _build_observed_people_directory(
            repository,
            guild,
            recent_messages=recent_messages,
            message=message,
        )

        self.assertEqual(len(result), 1)
        self.assertIn("<@847841141655076864>", result[0])
        self.assertIn("Cosmo Lord", result[0])
        self.assertIn("Задаёт ироничные вопросы", result[0])

    def test_build_target_subject_hint_matches_recent_participant_name(self) -> None:
        repository = ModerationRepository(Path(tempfile.mkdtemp()) / "moderation.sqlite3")
        repository.record_user_observation(
            guild_id=1,
            user_id=847841141655076864,
            author_name="Cosmo Lord",
            role_names=("Участник",),
            content="Алмасия — это страна захватившая африку",
            decision="allow",
            addressed_to_bot=False,
            labels=(),
        )
        repository.save_user_character_summary(
            guild_id=1,
            user_id=847841141655076864,
            summary="Задаёт ироничные вопросы ботам с условными ответами.",
        )

        guild = SimpleNamespace(
            id=1,
            members=(
                SimpleNamespace(id=847841141655076864, display_name="Cosmo Lord", name="cosmo_lord", roles=(SimpleNamespace(name="Участник"),)),
            ),
        )
        message = SimpleNamespace(
            author=SimpleNamespace(id=77),
            mentions=(),
            content="кто такой Cosmo Lord?",
        )
        recent_messages = [SimpleNamespace(author_id=847841141655076864)]

        result = _build_target_subject_hint(
            repository,
            guild,
            recent_messages=recent_messages,
            message=message,
        )

        self.assertIn("<@847841141655076864>", result)
        self.assertIn("Cosmo Lord", result)
        self.assertIn("@cosmo_lord", result)
        self.assertIn("Задаёт ироничные вопросы", result)

    def test_build_target_subject_hint_matches_cyrillic_transliterated_name(self) -> None:
        repository = ModerationRepository(Path(tempfile.mkdtemp()) / "moderation.sqlite3")
        repository.record_user_observation(
            guild_id=1,
            user_id=1018035964523839579,
            author_name="Katagan",
            role_names=("Участник",),
            content="Так ты мутить умеешь пиздабол",
            decision="light_violation",
            addressed_to_bot=True,
            labels=("insult",),
        )
        repository.save_user_character_summary(
            guild_id=1,
            user_id=1018035964523839579,
            summary="Использует игровой сленг, эмоциональные и провокационные фразы.",
        )

        guild = SimpleNamespace(
            id=1,
            members=(
                SimpleNamespace(
                    id=1018035964523839579,
                    display_name="Katagan",
                    name="katagan",
                    roles=(SimpleNamespace(name="Участник"),),
                ),
            ),
        )
        message = SimpleNamespace(
            author=SimpleNamespace(id=77),
            mentions=(),
            content="кто такой Катаган?",
        )
        recent_messages = [SimpleNamespace(author_id=1018035964523839579)]

        result = _build_target_subject_hint(
            repository,
            guild,
            recent_messages=recent_messages,
            message=message,
        )

        self.assertIn("<@1018035964523839579>", result)
        self.assertIn("Katagan", result)
        self.assertIn("эмоциональные и провокационные фразы", result)


if __name__ == "__main__":
    unittest.main()
