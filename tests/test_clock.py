from __future__ import annotations

from datetime import datetime, timezone
import unittest

from tests import support  # noqa: F401

from core.clock import convert_to_moscow


class ClockTests(unittest.TestCase):
    def test_naive_utc_time_is_converted_to_moscow(self) -> None:
        converted = convert_to_moscow(datetime(2026, 7, 30, 8, 0, 0))

        self.assertEqual(converted.hour, 11)
        self.assertIsNotNone(converted.tzinfo)

    def test_aware_time_is_converted_to_moscow(self) -> None:
        converted = convert_to_moscow(
            datetime(2026, 7, 30, 8, 0, 0, tzinfo=timezone.utc)
        )

        self.assertEqual(converted.hour, 11)
