from __future__ import annotations

import unittest
from types import SimpleNamespace

from tests import support  # noqa: F401
from modules.moderation.engagement import (
    is_low_signal_persona_message,
    is_bot_role_mentioned,
    should_skip_recent_channel_duplicate_reply,
    is_textually_addressed_to_bot,
    should_skip_duplicate_persona_reply,
)


class ModerationEngagementTests(unittest.TestCase):
    def test_duplicate_persona_reply_is_suppressed_only_for_same_user_turn(self) -> None:
        result = should_skip_duplicate_persona_reply(
            current_user_content="@bot ку",
            previous_user_content="@bot ку",
            previous_bot_reply="Ку. Живой пока.",
            candidate_reply="Ку. Живой пока.",
            reaction_emoji="",
            previous_remembered_at=2_000_000_000,
        )

        self.assertTrue(result)

    def test_duplicate_persona_reply_is_not_suppressed_when_turn_changed(self) -> None:
        result = should_skip_duplicate_persona_reply(
            current_user_content="@bot ку",
            previous_user_content="@bot ты тут?",
            previous_bot_reply="Ку. Живой пока.",
            candidate_reply="Ку. Живой пока.",
            reaction_emoji="",
            previous_remembered_at=2_000_000_000,
        )

        self.assertFalse(result)

    def test_reaction_keeps_reply_from_being_suppressed(self) -> None:
        result = should_skip_duplicate_persona_reply(
            current_user_content="@bot ку",
            previous_user_content="@bot ку",
            previous_bot_reply="Ку. Живой пока.",
            candidate_reply="Ку. Живой пока.",
            reaction_emoji="👋",
            previous_remembered_at=2_000_000_000,
        )

        self.assertFalse(result)

    def test_old_duplicate_turn_is_not_suppressed(self) -> None:
        result = should_skip_duplicate_persona_reply(
            current_user_content="@bot ку",
            previous_user_content="@bot ку",
            previous_bot_reply="Ку. Живой пока.",
            candidate_reply="Ку. Живой пока.",
            reaction_emoji="",
            previous_remembered_at=1,
        )

        self.assertFalse(result)

    def test_textual_address_detection_accepts_bracketed_bot_name(self) -> None:
        message = SimpleNamespace(content="@[Warlords] ку")
        bot_user = SimpleNamespace(name="Warlords", global_name=None)
        bot_member = SimpleNamespace(display_name="[Warlords]", nick="[Warlords]")

        result = is_textually_addressed_to_bot(message, bot_user=bot_user, bot_member=bot_member)

        self.assertTrue(result)

    def test_low_signal_persona_message_detects_single_emoji(self) -> None:
        self.assertTrue(is_low_signal_persona_message("👍"))
        self.assertFalse(is_low_signal_persona_message("когда сервер?"))

    def test_recent_channel_duplicate_reply_is_suppressed_for_low_signal_followup(self) -> None:
        result = should_skip_recent_channel_duplicate_reply(
            candidate_reply="Ну, закопал так закопал. Главное, чтобы не на сервере.",
            recent_channel_replies=("Ну, закопал так закопал. Главное, чтобы не на сервере.",),
            current_user_content="👍",
        )

        self.assertTrue(result)

    def test_recent_channel_duplicate_reply_is_not_suppressed_for_meaningful_followup(self) -> None:
        result = should_skip_recent_channel_duplicate_reply(
            candidate_reply="Ну, закопал так закопал. Главное, чтобы не на сервере.",
            recent_channel_replies=("Ну, закопал так закопал. Главное, чтобы не на сервере.",),
            current_user_content="а почему не на сервере?",
        )

        self.assertFalse(result)


    def test_role_mention_of_bot_role_counts_as_addressing_bot(self) -> None:
        message = SimpleNamespace(
            role_mentions=(SimpleNamespace(id=42, name="[Warlords]"),),
        )
        bot_member = SimpleNamespace(
            roles=(SimpleNamespace(id=7, name="@everyone"), SimpleNamespace(id=42, name="[Warlords]")),
        )

        result = is_bot_role_mentioned(
            message,
            bot_user=SimpleNamespace(name="Warlords", global_name=None),
            bot_member=bot_member,
        )

        self.assertTrue(result)

    def test_role_mention_with_bot_name_counts_even_if_role_is_not_on_bot(self) -> None:
        message = SimpleNamespace(
            role_mentions=(SimpleNamespace(id=99, name="[Warlords]"),),
        )
        bot_member = SimpleNamespace(
            display_name="[Warlords]",
            nick="[Warlords]",
            roles=(SimpleNamespace(id=7, name="@everyone"),),
        )

        result = is_bot_role_mentioned(
            message,
            bot_user=SimpleNamespace(name="Warlords", global_name=None),
            bot_member=bot_member,
        )

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
