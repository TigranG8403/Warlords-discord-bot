from __future__ import annotations

import io
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import discord

try:
    from PIL import Image, ImageFilter, ImageOps, ImageStat
except ImportError:  # pragma: no cover - exercised indirectly when Pillow is unavailable
    Image = None
    ImageFilter = None
    ImageOps = None
    ImageStat = None


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
OCR_HINT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("brand_1win", re.compile(r"\b1win\b", re.IGNORECASE)),
    ("brand_1xbet", re.compile(r"\b1xbet\b", re.IGNORECASE)),
    ("brand_mellstroy", re.compile(r"\bmell(?:i|s)?troy\w*\b|\bmeli(?:coins)?\b|\bmel(?:l|t)\s?coins?\b|меллстрой", re.IGNORECASE)),
    ("brand_cenatwin", re.compile(r"\bcenatwin\b", re.IGNORECASE)),
    ("casino", re.compile(r"\bcasino\b|казино", re.IGNORECASE)),
    ("crypto", re.compile(r"\bcrypto\b|крипт", re.IGNORECASE)),
    ("bonus", re.compile(r"\bbonus(?:es)?\b|бонус", re.IGNORECASE)),
    ("withdraw", re.compile(r"\bwithdraw(?:al)?\b|вывод|выплат", re.IGNORECASE)),
    ("deposit", re.compile(r"\bdeposit\b|депозит|пополн", re.IGNORECASE)),
    ("promo_code", re.compile(r"\bpromo ?code\b|промокод|код", re.IGNORECASE)),
    ("activate_code", re.compile(r"\bactivate code\b|активир", re.IGNORECASE)),
    ("claim_reward", re.compile(r"\bclaim your reward\b|получ", re.IGNORECASE)),
    ("register", re.compile(r"\bregister(?:s|ed|ing)?\b|регист", re.IGNORECASE)),
    ("rakeback", re.compile(r"\brakeback\b", re.IGNORECASE)),
    ("verification", re.compile(r"\bverification\b|вериф", re.IGNORECASE)),
    ("transactions", re.compile(r"\btransactions?\b|транзак", re.IGNORECASE)),
    ("wallet", re.compile(r"\bwallet\b|кошел", re.IGNORECASE)),
    ("balance", re.compile(r"\bbalance\b|баланс", re.IGNORECASE)),
    ("money_amount", re.compile(r"[$€₽]\s?\d|\b\d[\d,.]{2,}\s?(?:usd|eur|rub|руб|р)\b", re.IGNORECASE)),
    ("suspicious_domain", re.compile(r"\b[a-z0-9-]{4,}\.(?:com|net|org|io|gg)\b", re.IGNORECASE)),
)
META_MODERATION_MARKERS: tuple[str, ...] = (
    "нужна ручная проверка",
    "автомут",
    "автобан",
    "нарушитель",
    "канал",
    "решение",
    "причина",
    "метки",
    "источник",
    "timeout",
    "доказательства",
    "теги участников",
)


class AttachmentOcrService:
    def __init__(self, *, languages: str = "rus+eng", max_images: int = 8, timeout_seconds: int = 20) -> None:
        self.languages = languages
        self.max_images = max(1, max_images)
        self.timeout_seconds = max(5, timeout_seconds)
        self._available: bool | None = None

    def is_available(self) -> bool:
        if self._available is None:
            self._available = all(
                item is not None for item in (shutil.which("tesseract"), Image, ImageFilter, ImageOps, ImageStat)
            )
        return self._available

    def should_scan_attachment(self, attachment: discord.Attachment) -> bool:
        suffix = Path(attachment.filename).suffix.lower()
        return suffix in IMAGE_SUFFIXES

    def extract_texts(self, attachments: list[discord.Attachment]) -> tuple[str, ...]:
        if not self.is_available():
            return ()

        results: list[str] = []
        scanned = 0
        for attachment in attachments:
            if scanned >= self.max_images:
                break
            if not self.should_scan_attachment(attachment):
                continue
            text = self._extract_text_from_url(attachment.url)
            if text:
                results.append(text[:1500])
            scanned += 1
        return tuple(results)

    def _extract_text_from_url(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": "WarlordsBotOCR/1.0"})
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            raw = response.read()

        with Image.open(io.BytesIO(raw)) as image:
            prepared = self._prepare_image(image)
            with tempfile.TemporaryDirectory(prefix="warlords-ocr-") as temp_dir:
                input_path = Path(temp_dir) / "input.png"
                prepared.save(input_path, format="PNG")
                primary = self._run_tesseract(input_path, page_segmentation_mode="6")
                fallback = ""
                if len(primary) < 180:
                    fallback = self._run_tesseract(input_path, page_segmentation_mode="11")
        combined = _normalize_ocr_text(" ".join(part for part in (primary, fallback) if part))
        if not combined:
            return ""
        hint_tokens = _extract_ocr_hint_tokens(combined)
        if not hint_tokens:
            return combined
        hint_suffix = ", ".join(hint_tokens)
        return f"{combined} [ocr_hints: {hint_suffix}]"

    def _prepare_image(self, image: Image.Image) -> Image.Image:
        # Many scam screenshots use dark UI with light text. Invert them when needed so Tesseract sees dark text on light background.
        normalized = ImageOps.exif_transpose(image).convert("L")
        brightness = ImageStat.Stat(normalized).mean[0]
        if brightness < 118:
            normalized = ImageOps.invert(normalized)
        contrasted = ImageOps.autocontrast(normalized)
        scale = 3 if max(contrasted.size) < 1600 else 2
        enlarged = contrasted.resize((contrasted.width * scale, contrasted.height * scale))
        sharpened = enlarged.filter(ImageFilter.SHARPEN)
        return ImageOps.autocontrast(sharpened)

    def _run_tesseract(self, input_path: Path, *, page_segmentation_mode: str) -> str:
        completed = subprocess.run(
            [
                "tesseract",
                str(input_path),
                "stdout",
                "-l",
                self.languages,
                "--psm",
                page_segmentation_mode,
            ],
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            return ""
        return completed.stdout


def _normalize_ocr_text(text: str) -> str:
    collapsed = " ".join(text.split())
    return collapsed[:2200]


def _extract_ocr_hint_tokens(text: str) -> tuple[str, ...]:
    normalized = text.lower()
    hints: list[str] = []
    for label, pattern in OCR_HINT_PATTERNS:
        if pattern.search(normalized):
            hints.append(label)
    return tuple(hints)


def looks_like_meta_moderation_ocr(text: str) -> bool:
    normalized = text.lower()
    hits = sum(1 for marker in META_MODERATION_MARKERS if marker in normalized)
    return hits >= 3
