from __future__ import annotations

import discord


EMBED_COLOR = 0x6D1A1A


def build_warning_embed(moderated_count: int) -> discord.Embed:
    embed = discord.Embed(
        title="🪰 Мухоловка",
        description=(
            "Этот канал является автоматической ловушкой для спам-ботов.\n\n"
            "**Не отправляйте сюда сообщения.** Любое сообщение будет удалено, "
            "а к его автору автоматически применится наказание."
        ),
        color=EMBED_COLOR,
    )
    embed.set_footer(text=f"Поймано мух: {moderated_count}")
    return embed

