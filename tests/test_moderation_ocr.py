from __future__ import annotations

import unittest

from tests import support  # noqa: F401
from modules.moderation.ocr import _extract_ocr_hint_tokens, _normalize_ocr_text, looks_like_meta_moderation_ocr


class ModerationOcrTests(unittest.TestCase):
    def test_normalize_ocr_text_collapses_whitespace(self) -> None:
        normalized = _normalize_ocr_text("bonus   code \n withdraw \t now")

        self.assertEqual(normalized, "bonus code withdraw now")

    def test_extract_ocr_hint_tokens_detects_casino_signals(self) -> None:
        hints = _extract_ocr_hint_tokens(
            "Go to cenatwin.com, enter the promo code, receive your $2500 bonus and withdraw instantly."
        )

        self.assertIn("brand_cenatwin", hints)
        self.assertIn("promo_code", hints)
        self.assertIn("bonus", hints)
        self.assertIn("withdraw", hints)
        self.assertIn("money_amount", hints)
        self.assertIn("suspicious_domain", hints)

    def test_extract_ocr_hint_tokens_recognizes_mell_coins_variant(self) -> None:
        hints = _extract_ocr_hint_tokens("Баланс 10822.54 P Mell Coins")

        self.assertIn("brand_mellstroy", hints)
        self.assertIn("balance", hints)

    def test_meta_moderation_ocr_is_detected(self) -> None:
        self.assertTrue(
            looks_like_meta_moderation_ocr(
                "Нужна ручная проверка Нарушитель Канал Решение Причина Метки Источник Timeout"
            )
        )


if __name__ == "__main__":
    unittest.main()
