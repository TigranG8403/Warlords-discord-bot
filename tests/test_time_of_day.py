from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests import support  # noqa: F401

from core.time_of_day import period_key, pick_banner_asset_path, pick_by_period


class TimeOfDayTests(unittest.TestCase):
    def test_period_key_boundaries(self) -> None:
        cases = {
            5: "night",
            6: "morning",
            11: "morning",
            12: "day",
            17: "day",
            18: "evening",
            22: "evening",
            23: "night",
        }

        for hour, expected in cases.items():
            with self.subTest(hour=hour):
                self.assertEqual(period_key(datetime(2026, 1, 1, hour, 0, 0)), expected)

    def test_pick_by_period_uses_fallback_order(self) -> None:
        result = pick_by_period(
            datetime(2026, 1, 1, 19, 0, 0),
            {
                "morning": "morning",
                "day": None,
                "evening": None,
                "night": "night",
            },
        )

        self.assertEqual(result, "morning")

    def test_pick_banner_asset_path_returns_first_existing_fallback(self) -> None:
        with TemporaryDirectory() as temp_dir:
            assets_dir = Path(temp_dir)
            day_asset = assets_dir / "minecraft_day_1500x500.png"
            day_asset.write_bytes(b"test")

            selected = pick_banner_asset_path(
                assets_dir=assets_dir,
                stem="minecraft",
                current_time=datetime(2026, 1, 1, 8, 0, 0),
            )

            self.assertEqual(selected, day_asset)


if __name__ == "__main__":
    unittest.main()
