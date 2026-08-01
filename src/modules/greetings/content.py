from __future__ import annotations


ONBOARDING_CHANNEL_ID = 1343124803858599977
EMBED_COLOR = 0x831818
BANNER_FILENAME_TEMPLATE = "greeting_{member_id}.png"
DISCORD_USER_URL_TEMPLATE = "https://discord.com/users/{member_id}"
_MARKDOWN_CHARACTERS = frozenset(r"\`*_{}[]()#+-.!|>~")


def build_embed_description(*, member_id: int, display_name: str) -> str:
    member_link = build_member_profile_link(
        member_id=member_id,
        display_name=display_name,
    )
    return (
        f"## Добро пожаловать, {member_link}!\n\n"
        "Рады видеть тебя на Warlords.\n\n"
        "Познакомиться с проектом и узнать, с чего начать, можно в "
        f"<#{ONBOARDING_CHANNEL_ID}>."
    )


def build_member_profile_link(*, member_id: int, display_name: str) -> str:
    """Build a stable label that remains readable after a member leaves."""
    normalized_name = " ".join(display_name.split()).lstrip("@").strip()
    if not normalized_name:
        normalized_name = "участник"

    safe_name = "".join(
        f"\\{character}" if character in _MARKDOWN_CHARACTERS else character
        for character in normalized_name[:64]
    )
    safe_name = safe_name.replace("@", "@\u200b")
    profile_url = DISCORD_USER_URL_TEMPLATE.format(member_id=member_id)
    return f"[@\u200b{safe_name}]({profile_url})"
