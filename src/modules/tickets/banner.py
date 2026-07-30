from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import discord

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSETS_FONTS_DIR = PROJECT_ROOT / "assets" / "fonts"


def make_banner_file(
    *,
    asset_path: Path | None,
    text: str | None,
    filename: str,
    font_paths: tuple[Path, ...] | None = None,
    font_weight: int | None = None,
) -> discord.File | None:
    if asset_path is None:
        return None

    try:
        from PIL import Image, ImageDraw
    except ModuleNotFoundError:
        logger.warning("Локальный баннер не будет сгенерирован: Pillow не установлен.")
        return None

    try:
        with Image.open(asset_path) as source_image:
            image = source_image.convert("RGBA")
    except OSError as error:
        logger.warning("Не удалось открыть исходное изображение баннера %s: %s", asset_path, error)
        return None

    if text:
        draw = ImageDraw.Draw(image)
        font = _fit_banner_font(
            draw,
            text,
            image.width,
            image.height,
            font_paths=font_paths,
            font_weight=font_weight,
        )
        text_bbox = draw.textbbox((0, 0), text, font=font, stroke_width=2)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        text_x = (image.width - text_width) / 2
        text_y = (image.height - text_height) / 2 - 8
        shadow_offset = max(3, image.width // 360)
        draw.text(
            (text_x + shadow_offset, text_y + shadow_offset),
            text,
            font=font,
            fill=(0, 0, 0, 92),
            stroke_width=0,
        )
        draw.text(
            (text_x, text_y),
            text,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=2,
            stroke_fill=(0, 0, 0, 110),
        )

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return discord.File(output, filename=filename)


def _fit_banner_font(
    draw,
    text: str,
    image_width: int,
    image_height: int,
    *,
    font_paths: tuple[Path, ...] | None,
    font_weight: int | None,
):
    from PIL import ImageFont

    font_candidates = font_paths or tuple(_font_candidates())
    max_width = int(image_width * 0.72)
    max_height = int(image_height * 0.34)
    start_size = max(52, image_width // 7)

    for font_path in font_candidates:
        if not font_path.exists():
            continue

        for font_size in range(start_size, 35, -4):
            try:
                font = ImageFont.truetype(str(font_path), font_size)
                if font_weight is not None:
                    font.set_variation_by_axes([font_weight])
            except OSError:
                continue

            text_bbox = draw.textbbox((0, 0), text, font=font, stroke_width=4)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            if text_width <= max_width and text_height <= max_height:
                return font

    return ImageFont.load_default()


def _font_candidates() -> list[Path]:
    return [
        ASSETS_FONTS_DIR / "medieval-sharp.bold.ttf",
        ASSETS_FONTS_DIR / "medieval-sharp-regular.ttf",
        Path("C:/Windows/Fonts/seguisb.ttf"),
        Path("C:/Windows/Fonts/trebucbd.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    ]
