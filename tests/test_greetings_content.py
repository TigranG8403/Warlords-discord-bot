from __future__ import annotations

import unittest

from tests import support  # noqa: F401

from modules.greetings.content import (
    build_embed_description,
    fallback_line,
    sanitize_generated_line,
)
from modules.greetings.service import banner_name


class GreetingsContentTests(unittest.TestCase):
    def test_clean_ai_line_is_normalized(self) -> None:
        self.assertEqual(
            sanitize_generated_line("  Писарь уже нашёл свободную строку в городском реестре  "),
            "Писарь уже нашёл свободную строку в городском реестре.",
        )

    def test_pompous_or_mentioning_line_is_rejected(self) -> None:
        self.assertIsNone(
            sanitize_generated_line("Тебе суждено вершить историю этого великого мира.")
        )
        self.assertIsNone(
            sanitize_generated_line("Новый человек уже ждёт тебя в <#123456789>.")
        )

    def test_fallback_is_stable_for_member(self) -> None:
        self.assertEqual(fallback_line(123), fallback_line(123))

    def test_embed_contains_safe_member_and_onboarding_mentions(self) -> None:
        description = build_embed_description(member_mention="<@123>", line="Ворота открыты.")

        self.assertIn("<@123>", description)
        self.assertIn("<#1343124803858599977>", description)

    def test_banner_name_removes_unsupported_symbols_and_limits_length(self) -> None:
        self.assertEqual(banner_name("  Sir 🐦🔥 Messire  "), "Sir Messire")
        self.assertLessEqual(len(banner_name("ОченьДлинноеИмя" * 4)), 28)
