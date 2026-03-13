from __future__ import annotations

import logging

import discord
from discord.ui import Button, Modal, Select, TextInput, View

from core.discord_interactions import (
    safe_response_edit_message,
    safe_response_send_message,
    safe_response_send_modal,
)

from ..catalog import (
    PANEL_FRACTION,
    PANEL_RP,
    PANEL_SUPPORT,
    PanelSpec,
    ROOT_PANEL,
    TicketTypeSpec,
    get_panel,
    iter_panels,
    iter_ticket_types,
)
from ..service import TicketService

logger = logging.getLogger(__name__)


async def _safe_send_message(interaction: discord.Interaction, *args, **kwargs) -> bool:
    return await safe_response_send_message(interaction, *args, **kwargs)


async def _safe_send_modal(interaction: discord.Interaction, modal: Modal) -> bool:
    return await safe_response_send_modal(interaction, modal)


async def _safe_edit_message(interaction: discord.Interaction, **kwargs) -> bool:
    return await safe_response_edit_message(interaction, **kwargs)


class TicketRequestModal(Modal):
    def __init__(self, service: TicketService, ticket_type: TicketTypeSpec):
        super().__init__(title=ticket_type.modal_title)
        self.service = service
        self.ticket_type = ticket_type
        self.inputs: dict[str, TextInput] = {}

        for field in ticket_type.fields:
            input_field = TextInput(
                label=field.label,
                placeholder=field.placeholder,
                style=field.style,
                required=field.required,
                max_length=field.max_length,
            )
            self.inputs[field.key] = input_field
            self.add_item(input_field)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        submission = {
            key: text_input.value.strip()
            for key, text_input in self.inputs.items()
            if text_input.value is not None and text_input.value.strip()
        }
        await self.service.create_ticket(interaction, self.ticket_type, submission)


class TicketCategoryPickerView(View):
    def __init__(self, service: TicketService):
        super().__init__(timeout=120)
        self.service = service

        description_map = {
            PANEL_SUPPORT: "Жалобы, проходки, баги и другие вопросы.",
            PANEL_FRACTION: "Заявка на рекламу фракции.",
            PANEL_RP: "RP-регистрации и RP-вопросы.",
        }

        options = [
            discord.SelectOption(
                label=panel.label,
                value=panel.key,
                description=description_map.get(panel.key, panel.label),
                emoji=panel.button_emoji,
            )
            for panel in iter_panels()
        ]

        select = Select(
            placeholder="Выберите категорию",
            options=options,
            min_values=1,
            max_values=1,
        )
        select.callback = self._show_ticket_types
        self.add_item(select)

    async def _show_ticket_types(self, interaction: discord.Interaction) -> None:
        select = self.children[0]
        if not isinstance(select, Select):
            await _safe_send_message(interaction, "⚠️ Не удалось обработать выбор.", ephemeral=True)
            return

        panel_key = select.values[0]
        ticket_types = iter_ticket_types(panel_key)
        if len(ticket_types) == 1:
            await _safe_send_modal(interaction, TicketRequestModal(self.service, ticket_types[0]))
            return

        await _safe_edit_message(
            interaction,
            content=f"Категория: **{get_panel(panel_key).label}**. Теперь выберите тип обращения.",
            view=TicketTypePickerView(self.service, panel_key),
        )


class TicketTypeSelect(Select):
    def __init__(self, service: TicketService, panel_key: str):
        self.service = service
        self.panel_key = panel_key

        options = [
            discord.SelectOption(
                label=ticket_type.label,
                value=ticket_type.key,
                description=ticket_type.description,
                emoji=ticket_type.emoji,
            )
            for ticket_type in iter_ticket_types(panel_key)
        ]

        super().__init__(
            placeholder="Выберите тип обращения",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        ticket_type = next(
            ticket_type
            for ticket_type in iter_ticket_types(self.panel_key)
            if ticket_type.key == self.values[0]
        )

        if not await _safe_send_modal(interaction, TicketRequestModal(self.service, ticket_type)):
            return

        message = interaction.message
        if message is None or message.flags.ephemeral:
            return

        try:
            await message.edit(view=TicketTypePickerView(self.service, self.panel_key))
        except discord.NotFound:
            return
        except (discord.Forbidden, discord.HTTPException) as error:
            logger.warning("Не удалось обновить dropdown выбора типа тикета: %s", error)


class TicketTypePickerView(View):
    def __init__(self, service: TicketService, panel_key: str):
        super().__init__(timeout=120)
        self.service = service
        self.panel_key = panel_key

        self.add_item(TicketTypeSelect(service, panel_key))


class TicketPanelView(View):
    def __init__(self, service: TicketService):
        super().__init__(timeout=None)
        self.service = service
        self.panel_key = ROOT_PANEL
        panel = get_panel(ROOT_PANEL)

        open_button = Button(
            label=panel.button_label,
            style=discord.ButtonStyle.success,
            emoji=panel.button_emoji,
            custom_id="open_ticket_panel:root",
        )
        open_button.callback = self._open_panel
        self.add_item(open_button)

    async def _open_panel(self, interaction: discord.Interaction) -> None:
        await _safe_send_message(
            interaction,
            "Сначала выберите категорию обращения.",
            view=TicketCategoryPickerView(self.service),
            ephemeral=True,
        )


def build_panel_embed(panel: PanelSpec, image_url: str | None, color: int) -> discord.Embed:
    embed = discord.Embed(
        title=panel.title,
        description=panel.description,
        color=color,
    )
    if image_url:
        embed.set_image(url=image_url)
    return embed
