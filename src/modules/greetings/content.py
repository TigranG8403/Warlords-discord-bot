from __future__ import annotations


ONBOARDING_CHANNEL_ID = 1343124803858599977
EMBED_COLOR = 0x831818
BANNER_FILENAME_TEMPLATE = "greeting_{member_id}.png"


def build_embed_description(*, member_mention: str) -> str:
    return (
        f"## Добро пожаловать, {member_mention}!\n\n"
        "Рады видеть тебя на Warlords.\n\n"
        "Познакомиться с проектом и узнать, с чего начать, можно в "
        f"<#{ONBOARDING_CHANNEL_ID}>."
    )
