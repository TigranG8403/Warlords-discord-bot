from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from tests import support  # noqa: F401

from modules.greetings.banner import make_greeting_banner_file


class GreetingsBannerTests(unittest.TestCase):
    def test_banner_renders_avatar_and_cyrillic_name(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            background_path = root / "background.png"
            Image.new("RGB", (1500, 500), (52, 59, 67)).save(background_path)

            avatar_buffer = BytesIO()
            Image.new("RGB", (256, 256), (131, 24, 24)).save(
                avatar_buffer,
                format="PNG",
            )
            banner = make_greeting_banner_file(
                asset_path=background_path,
                avatar_bytes=avatar_buffer.getvalue(),
                display_name="Андрей Мессир",
                filename="preview.png",
            )

            self.assertIsNotNone(banner)
            with Image.open(banner.fp) as rendered:
                self.assertEqual(rendered.size, (1500, 500))
