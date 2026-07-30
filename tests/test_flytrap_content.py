from __future__ import annotations

import unittest

import discord

from tests import support  # noqa: F401

from modules.flytrap.content import build_warning_view


class FlytrapContentTests(unittest.TestCase):
    def test_warning_uses_compact_components_v2_layout(self) -> None:
        view = build_warning_view(12)

        self.assertIsInstance(view, discord.ui.LayoutView)
        container = view.children[0]
        self.assertIsInstance(container, discord.ui.Container)

        text = container.children[0]
        self.assertIsInstance(text, discord.ui.TextDisplay)
        self.assertIn("НЕ ОТПРАВЛЯЙТЕ СООБЩЕНИЯ", text.content)
        self.assertNotIn("бан", text.content.casefold())
        self.assertNotIn("наказан", text.content.casefold())

        action_row = container.children[1]
        self.assertIsInstance(action_row, discord.ui.ActionRow)
        counter = action_row.children[0]
        self.assertIsInstance(counter, discord.ui.Button)
        self.assertEqual(counter.label, "Мух: 12")
        self.assertTrue(counter.disabled)


if __name__ == "__main__":
    unittest.main()
