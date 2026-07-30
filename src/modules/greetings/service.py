from __future__ import annotations

import datetime as dt
import unicodedata
from pathlib import Path

import discord

from core.clock import get_moscow_time
from core.time_of_day import pick_banner_asset_path
from modules.tickets.banner import make_banner_file

from .content import (
    BANNER_FILENAME_TEMPLATE,
    EMBED_COLOR,
    build_embed_description,
)
from .copywriter import GreetingCopywriter


GREETING_FONT_PATH = (
    Path(__file__).resolve().parents[3]
    / "assets"
    / "fonts"
    / "cormorant-infant.ttf"
)


class GreetingsService:
    def __init__(self, *, assets_dir: Path, copywriter: GreetingCopywriter) -> None:
        self._assets_dir = assets_dir
        self._copywriter = copywriter

    async def send_greeting(
        self,
        channel: discord.TextChannel,
        member: discord.Member,
        *,
        current_time: dt.datetime | None = None,
    ) -> discord.Message:
        effective_time = current_time or get_moscow_time()
        line = await self._copywriter.create_line(
            member_id=member.id,
            current_time=effective_time,
        )
        filename = BANNER_FILENAME_TEMPLATE.format(member_id=member.id)
        banner = make_banner_file(
            asset_path=pick_banner_asset_path(
                assets_dir=self._assets_dir,
                stem="minecraft",
                current_time=effective_time,
            ),
            text=banner_name(member.display_name),
            filename=filename,
            font_paths=(GREETING_FONT_PATH,),
            font_weight=700,
        )

        embed = discord.Embed(
            description=build_embed_description(
                member_mention=member.mention,
                line=line,
            ),
            color=EMBED_COLOR,
        )
        if banner is not None:
            embed.set_image(url=f"attachment://{filename}")

        send_options = {
            "embed": embed,
            "allowed_mentions": discord.AllowedMentions(
                everyone=False,
                roles=False,
                users=[member],
                replied_user=False,
            ),
        }
        if banner is not None:
            send_options["file"] = banner
        return await channel.send(**send_options)


def banner_name(display_name: str) -> str:
    normalized = " ".join(display_name.split())
    clean = "".join(
        character
        for character in normalized
        if unicodedata.category(character)[0] in {"L", "N"}
        or character in " ._-'"
    ).strip()
    clean = " ".join(clean.split())
    if not clean:
        return "Новый участник"
    if len(clean) <= 28:
        return clean
    return f"{clean[:27].rstrip()}…"
