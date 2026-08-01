from __future__ import annotations

import unittest

from tests import support  # noqa: F401

from modules.greetings.banner import banner_name
from modules.greetings.content import build_embed_description, build_member_profile_link


class GreetingsContentTests(unittest.TestCase):
    def test_embed_contains_stable_member_link_and_onboarding_mention(self) -> None:
        description = build_embed_description(member_id=123, display_name="Messire")

        self.assertNotIn("<@123>", description)
        self.assertIn("https://discord.com/users/123", description)
        self.assertIn("Messire", description)
        self.assertIn("<#1343124803858599977>", description)
        self.assertIn("Рады видеть тебя на Warlords.", description)

    def test_banner_name_removes_unsupported_symbols_and_limits_length(self) -> None:
        self.assertEqual(banner_name("  Sir 🐦🔥 Messire  "), "Sir Messire")
        self.assertLessEqual(len(banner_name("ОченьДлинноеИмя" * 4)), 32)

    def test_banner_name_normalizes_decorative_letters_and_uses_fallback(self) -> None:
        ascii_only = lambda character: character.isascii()

        self.assertEqual(banner_name("𝕮𝕺𝕾𝕸𝕺𝕾"), "COSMOS")
        self.assertEqual(
            banner_name(
                "𐍈𐍈",
                fallback_name="cosmos_1",
                supports_character=ascii_only,
            ),
            "cosmos_1",
        )

    def test_member_profile_link_escapes_markdown_and_mentions(self) -> None:
        link = build_member_profile_link(
            member_id=123,
            display_name=" @everyone [test] ",
        )

        self.assertNotIn("<@123>", link)
        self.assertNotIn("@everyone", link)
        self.assertIn("https://discord.com/users/123", link)
        self.assertIn(r"\[test\]", link)
