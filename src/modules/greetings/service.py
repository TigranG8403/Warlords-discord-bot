from __future__ import annotations

import datetime as dt
from pathlib import Path

import discord

from core.clock import get_moscow_time
from core.time_of_day import pick_banner_asset_path

from .banner import make_greeting_banner_file
from .content import BANNER_FILENAME_TEMPLATE, EMBED_COLOR, build_embed_description


class GreetingsService:
    def __init__(self, *, assets_dir: Path) -> None:
        self._assets_dir = assets_dir

    async def send_greeting(
        self,
        channel: discord.TextChannel,
        member: discord.Member,
        *,
        current_time: dt.datetime | None = None,
    ) -> discord.Message:
        effective_time = current_time or get_moscow_time()
        filename = BANNER_FILENAME_TEMPLATE.format(member_id=member.id)
        banner = make_greeting_banner_file(
            asset_path=pick_banner_asset_path(
                assets_dir=self._assets_dir,
                stem="minecraft",
                current_time=effective_time,
            ),
            avatar_bytes=await _read_avatar(member),
            display_name=member.display_name,
            fallback_name=member.name,
            filename=filename,
        )
        embed = discord.Embed(
            description=build_embed_description(
                member_id=member.id,
                display_name=member.display_name,
            ),
            color=EMBED_COLOR,
        )
        if banner is not None:
            embed.set_image(url=f"attachment://{filename}")

        send_options = {
            "embed": embed,
            "allowed_mentions": discord.AllowedMentions.none(),
        }
        if banner is not None:
            send_options["file"] = banner
        return await channel.send(**send_options)


async def _read_avatar(member: discord.Member) -> bytes | None:
    try:
        return await member.display_avatar.with_size(256).read()
    except (discord.HTTPException, OSError):
        return None
