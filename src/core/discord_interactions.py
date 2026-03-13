from __future__ import annotations

from typing import Any

import discord
from discord.ui import Modal


def is_acknowledged_interaction_error(error: BaseException) -> bool:
    return isinstance(error, discord.HTTPException) and getattr(error, "code", None) == 40060


def is_unknown_interaction_error(error: BaseException) -> bool:
    return isinstance(error, discord.NotFound) and getattr(error, "code", None) == 10062


def is_ignorable_interaction_error(error: BaseException) -> bool:
    return is_acknowledged_interaction_error(error) or is_unknown_interaction_error(error)


async def safe_defer(
    interaction: discord.Interaction,
    *,
    ephemeral: bool = False,
    thinking: bool = False,
) -> bool:
    if interaction.response.is_done():
        return False

    try:
        await interaction.response.defer(ephemeral=ephemeral, thinking=thinking)
        return True
    except discord.NotFound:
        return False
    except discord.HTTPException as error:
        if is_acknowledged_interaction_error(error):
            return False
        raise


async def safe_response_send_message(
    interaction: discord.Interaction,
    *args: Any,
    **kwargs: Any,
) -> bool:
    if interaction.response.is_done():
        return False

    try:
        await interaction.response.send_message(*args, **kwargs)
        return True
    except discord.NotFound:
        return False
    except discord.HTTPException as error:
        if is_acknowledged_interaction_error(error):
            return False
        raise


async def safe_response_send_modal(interaction: discord.Interaction, modal: Modal) -> bool:
    if interaction.response.is_done():
        return False

    try:
        await interaction.response.send_modal(modal)
        return True
    except discord.NotFound:
        return False
    except discord.HTTPException as error:
        if is_acknowledged_interaction_error(error):
            return False
        raise


async def safe_response_edit_message(
    interaction: discord.Interaction,
    **kwargs: Any,
) -> bool:
    if interaction.response.is_done():
        return False

    try:
        await interaction.response.edit_message(**kwargs)
        return True
    except discord.NotFound:
        return False
    except discord.HTTPException as error:
        if is_acknowledged_interaction_error(error):
            return False
        raise


async def safe_followup_send(
    interaction: discord.Interaction,
    *args: Any,
    **kwargs: Any,
) -> bool:
    try:
        await interaction.followup.send(*args, **kwargs)
        return True
    except discord.NotFound:
        return False
    except discord.HTTPException as error:
        if is_acknowledged_interaction_error(error):
            return False
        raise


async def safe_send_ephemeral(interaction: discord.Interaction, message: str) -> bool:
    if interaction.response.is_done():
        return await safe_followup_send(interaction, message, ephemeral=True)

    return await safe_response_send_message(interaction, message, ephemeral=True)
