from __future__ import annotations

import unittest

from tests import support  # noqa: F401

from modules.presence.module import _members_label


class PresenceModuleTests(unittest.TestCase):
    def test_members_label_declension(self) -> None:
        cases = {
            1: "участник",
            2: "участника",
            5: "участников",
            11: "участников",
            21: "участник",
            24: "участника",
            100: "участников",
        }

        for count, expected in cases.items():
            with self.subTest(count=count):
                self.assertEqual(_members_label(count), expected)


if __name__ == "__main__":
    unittest.main()
