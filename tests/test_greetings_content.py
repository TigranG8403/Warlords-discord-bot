from __future__ import annotations

import unittest

from tests import support  # noqa: F401

from modules.greetings.banner import banner_name
from modules.greetings.content import build_embed_description


class GreetingsContentTests(unittest.TestCase):
    def test_embed_contains_safe_member_and_onboarding_mentions(self) -> None:
        description = build_embed_description(member_mention="<@123>")

        self.assertIn("<@123>", description)
        self.assertIn("<#1343124803858599977>", description)
        self.assertIn("Рады видеть тебя на Warlords.", description)

    def test_banner_name_removes_unsupported_symbols_and_limits_length(self) -> None:
        self.assertEqual(banner_name("  Sir 🐦🔥 Messire  "), "Sir Messire")
        self.assertLessEqual(len(banner_name("ОченьДлинноеИмя" * 4)), 32)
