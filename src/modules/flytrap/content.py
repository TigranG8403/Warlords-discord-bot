from __future__ import annotations

import discord


PANEL_COLOR = 0x6D1A1A


def build_warning_view(moderated_count: int) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(
                "## НЕ ОТПРАВЛЯЙТЕ СООБЩЕНИЯ В ЭТОТ КАНАЛ\n\n"
                "Этот канал используется для ловли спам-ботов."
            ),
            discord.ui.ActionRow(
                discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label=f"Мух: {moderated_count}",
                    emoji="🪰",
                    disabled=True,
                )
            ),
            accent_color=PANEL_COLOR,
        )
    )
    return view
