from __future__ import annotations

import unittest

from tests import support  # noqa: F401
from modules.moderation.config import ModerationContextMessage, ModerationEvaluationInput
from modules.moderation.rules import evaluate_with_rules, should_consider_message_for_moderation


class ModerationRulesTests(unittest.TestCase):
    def test_candidate_detection_flags_obvious_insult(self) -> None:
        self.assertTrue(should_consider_message_for_moderation("иди нахуй, долбоеб"))

    def test_candidate_detection_ignores_plain_profanity_without_attack(self) -> None:
        self.assertFalse(should_consider_message_for_moderation("Десс добренький, он бы такую хуйню не высирал"))

    def test_candidate_detection_flags_suspicious_link(self) -> None:
        self.assertTrue(
            should_consider_message_for_moderation(
                "забирай бонус в казино https://discord.gg/test",
                mention_count=1,
            )
        )

    def test_rules_return_light_violation_for_direct_insult(self) -> None:
        decision = evaluate_with_rules(
            ModerationEvaluationInput(
                guild_id=1,
                guild_name="Warlords",
                channel_id=2,
                channel_name="chat",
                message_id=3,
                author_id=4,
                author_name="user",
                author_display_name="user",
                content="ты просто конченый долбоеб",
            )
        )

        self.assertEqual(decision.decision, "light_violation")
        self.assertEqual(decision.timeout_minutes, 180)
        self.assertIn("insult", decision.labels)

    def test_rules_return_ban_for_hate_violence(self) -> None:
        decision = evaluate_with_rules(
            ModerationEvaluationInput(
                guild_id=1,
                guild_name="Warlords",
                channel_id=2,
                channel_name="chat",
                message_id=3,
                author_id=4,
                author_name="user",
                author_display_name="user",
                content="жечь евреев",
            )
        )

        self.assertEqual(decision.decision, "ban_violation")
        self.assertIn("religion_attack", decision.labels)

    def test_rules_allow_server_question_with_plain_profanity(self) -> None:
        decision = evaluate_with_rules(
            ModerationEvaluationInput(
                guild_id=1,
                guild_name="Warlords",
                channel_id=2,
                channel_name="chat",
                message_id=3,
                author_id=4,
                author_name="user",
                author_display_name="user",
                content="когда открытие ебаного сервера?",
            )
        )

        self.assertEqual(decision.decision, "allow")

    def test_rules_return_ban_for_casino_promo(self) -> None:
        decision = evaluate_with_rules(
            ModerationEvaluationInput(
                guild_id=1,
                guild_name="Warlords",
                channel_id=2,
                channel_name="chat",
                message_id=3,
                author_id=4,
                author_name="user",
                author_display_name="user",
                content="забирай бонус казино 1win https://discord.gg/test",
            )
        )

        self.assertEqual(decision.decision, "ban_violation")
        self.assertTrue(decision.should_delete_message)

    def test_rules_return_ban_for_suspicious_ocr_casino_screenshot(self) -> None:
        decision = evaluate_with_rules(
            ModerationEvaluationInput(
                guild_id=1,
                guild_name="Warlords",
                channel_id=2,
                channel_name="chat",
                message_id=3,
                author_id=4,
                author_name="user",
                author_display_name="user",
                content="bro",
                attachment_filenames=("img.png",),
                attachment_ocr_texts=(
                    "claim your reward go to cenatwin.com enter the special promo code receive your $2500 bonus withdraw instantly "
                    "[ocr_hints: brand_cenatwin, bonus, withdraw, promo_code, claim_reward, register, money_amount, suspicious_domain]",
                ),
            )
        )

        self.assertEqual(decision.decision, "ban_violation")
        self.assertIn("ocr", decision.labels)

    def test_rules_return_alert_for_regular_advertising(self) -> None:
        decision = evaluate_with_rules(
            ModerationEvaluationInput(
                guild_id=1,
                guild_name="Warlords",
                channel_id=2,
                channel_name="chat",
                message_id=3,
                author_id=4,
                author_name="user",
                author_display_name="user",
                content="заходи к нам на сервер https://discord.gg/test",
                recent_messages=(
                    ModerationContextMessage(
                        author_id=4,
                        author_name="user",
                        content="там розыгрыш",
                        created_at=1,
                        is_target_author=True,
                    ),
                ),
            )
        )

        self.assertEqual(decision.decision, "scam_alert")
        self.assertTrue(decision.requires_admin_alert)

    def test_rules_allow_plain_profanity_without_personal_attack(self) -> None:
        decision = evaluate_with_rules(
            ModerationEvaluationInput(
                guild_id=1,
                guild_name="Warlords",
                channel_id=2,
                channel_name="chat",
                message_id=3,
                author_id=4,
                author_name="user",
                author_display_name="user",
                content="Десс добренький, он бы такую хуйню не высирал",
            )
        )

        self.assertEqual(decision.decision, "allow")


if __name__ == "__main__":
    unittest.main()
