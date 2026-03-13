from __future__ import annotations

import unittest

from tests import support  # noqa: F401

from modules.tickets.catalog import get_ticket_type
from modules.tickets.channel_ops import build_ticket_channel_name, derive_ticket_subject


class TicketChannelOpsTests(unittest.TestCase):
    def test_derive_ticket_subject_prefers_subject_fields(self) -> None:
        ticket_type = get_ticket_type("other")

        self.assertEqual(
            derive_ticket_subject(ticket_type, {"subject": "  Нужна помощь  ", "details": "Описание"}),
            "Нужна помощь",
        )
        self.assertEqual(
            derive_ticket_subject(ticket_type, {"fraction_name": "  Орден  ", "details": "Описание"}),
            "Орден",
        )
        self.assertEqual(
            derive_ticket_subject(ticket_type, {"city_name": "  Ривенхолл  ", "details": "Описание"}),
            "Ривенхолл",
        )

    def test_derive_ticket_subject_uses_first_non_empty_value_as_fallback(self) -> None:
        ticket_type = get_ticket_type("other")

        subject = derive_ticket_subject(ticket_type, {"details": "  Очень длинное описание  ", "extra": ""})

        self.assertEqual(subject, "Очень длинное описание")

    def test_build_ticket_channel_name_normalizes_and_limits_slug(self) -> None:
        self.assertEqual(
            build_ticket_channel_name("report", "Рыцарь", 123456789),
            "report-user-6789",
        )
        self.assertEqual(
            build_ticket_channel_name("report", "Sir Very Long Display Name", 987654321),
            "report-sir-very-long-displa-4321",
        )


if __name__ == "__main__":
    unittest.main()
