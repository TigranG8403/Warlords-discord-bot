from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
import unicodedata

import discord


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FONT_PATH = PROJECT_ROOT / "assets" / "fonts" / "noto-sans-semibold.ttf"


def make_greeting_banner_file(
    *,
    asset_path: Path | None,
    avatar_bytes: bytes | None,
    display_name: str,
    filename: str,
) -> discord.File | None:
    if asset_path is None:
        return None

    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
    except ModuleNotFoundError:
        logger.warning("Баннер приветствия не создан: Pillow не установлен.")
        return None

    try:
        with Image.open(asset_path) as source_image:
            image = source_image.convert("RGBA")
    except OSError as error:
        logger.warning("Не удалось открыть фон приветствия %s: %s", asset_path, error)
        return None

    draw = ImageDraw.Draw(image, "RGBA")
    name = banner_name(display_name)
    avatar_size = min(156, int(image.height * 0.34))
    avatar = (
        _prepare_avatar(
            Image=Image,
            ImageDraw=ImageDraw,
            ImageOps=ImageOps,
            avatar_bytes=avatar_bytes,
            size=avatar_size,
        )
        if avatar_bytes
        else None
    )
    gap = 36 if avatar is not None else 0
    font = _fit_font(
        ImageFont=ImageFont,
        draw=draw,
        text=name,
        max_width=int(image.width * 0.55),
        max_height=avatar_size,
    )
    text_box = draw.textbbox((0, 0), name, font=font, stroke_width=1)
    text_width = text_box[2] - text_box[0]
    text_height = text_box[3] - text_box[1]
    content_width = text_width + (avatar_size + gap if avatar is not None else 0)
    content_height = max(text_height, avatar_size if avatar is not None else 0)
    content_x = (image.width - content_width) / 2
    content_y = (image.height - content_height) / 2

    text_x = content_x
    shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer, "RGBA")
    if avatar is not None:
        shadow_draw.ellipse(
            (
                content_x + 2,
                content_y + 4,
                content_x + avatar_size + 6,
                content_y + avatar_size + 8,
            ),
            fill=(0, 0, 0, 175),
        )
        text_x += avatar_size + gap

    text_y = content_y + (content_height - text_height) / 2 - text_box[1]
    shadow_draw.text(
        (text_x + 3, text_y + 4),
        name,
        font=font,
        fill=(0, 0, 0, 220),
        stroke_width=2,
        stroke_fill=(0, 0, 0, 180),
    )
    image.alpha_composite(shadow_layer.filter(ImageFilter.GaussianBlur(radius=5)))
    draw = ImageDraw.Draw(image, "RGBA")

    if avatar is not None:
        image.alpha_composite(avatar, (round(content_x), round(content_y)))
        draw.ellipse(
            (
                content_x - 2,
                content_y - 2,
                content_x + avatar_size + 2,
                content_y + avatar_size + 2,
            ),
            outline=(255, 255, 255, 105),
            width=3,
        )

    draw.text(
        (text_x, text_y),
        name,
        font=font,
        fill=(244, 245, 247, 255),
        stroke_width=1,
        stroke_fill=(0, 0, 0, 115),
    )

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return discord.File(output, filename=filename)


def banner_name(display_name: str) -> str:
    normalized = " ".join(display_name.split())
    clean = "".join(
        character
        for character in normalized
        if unicodedata.category(character)[0] in {"L", "N"}
        or character in " ._-'"
    )
    clean = " ".join(clean.split()).strip()
    if not clean:
        return "Новый участник"
    if len(clean) <= 32:
        return clean
    return f"{clean[:31].rstrip()}…"


def _fit_font(*, ImageFont, draw, text: str, max_width: int, max_height: int):
    for font_size in range(116, 41, -3):
        try:
            font = ImageFont.truetype(str(FONT_PATH), font_size)
        except OSError:
            break
        box = draw.textbbox((0, 0), text, font=font, stroke_width=1)
        if box[2] - box[0] <= max_width and box[3] - box[1] <= max_height:
            return font
    return ImageFont.load_default()


def _prepare_avatar(*, Image, ImageDraw, ImageOps, avatar_bytes: bytes, size: int):
    try:
        with Image.open(BytesIO(avatar_bytes)) as source_avatar:
            avatar = ImageOps.fit(
                source_avatar.convert("RGBA"),
                (size, size),
                method=Image.Resampling.LANCZOS,
            )
    except OSError as error:
        logger.warning("Не удалось декодировать аватар для баннера: %s", error)
        return None

    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, size, size), fill=255)
    avatar.putalpha(mask)
    return avatar
