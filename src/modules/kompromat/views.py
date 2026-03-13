from __future__ import annotations

import discord
from discord.ui import Button, Modal, Select, TextInput, UserSelect, View

from core.discord_interactions import (
    safe_defer,
    safe_followup_send,
    safe_response_edit_message,
    safe_response_send_message,
    safe_response_send_modal,
)

from .service import KompromatService


class EvidenceThreadView(View):
    def __init__(self, thread_url: str):
        super().__init__(timeout=300)
        self.add_item(
            Button(
                label="Открыть тред доказательств",
                style=discord.ButtonStyle.link,
                url=thread_url,
            )
        )


class KompromatCreateModal(Modal):
    def __init__(self, service: KompromatService, category_key: str, tagged_user_ids: list[int]):
        super().__init__(title="Новый компромат")
        self.service = service
        self.category_key = category_key
        self.tagged_user_ids = tagged_user_ids

        self.title_input = TextInput(
            label="Короткий заголовок",
            placeholder="Например: подозрительная переписка",
            max_length=100,
        )
        self.summary_input = TextInput(
            label="Суть",
            placeholder="Кратко опишите, что произошло и почему это важно",
            style=discord.TextStyle.paragraph,
            max_length=1000,
        )

        self.add_item(self.title_input)
        self.add_item(self.summary_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not await safe_defer(interaction, ephemeral=True, thinking=True):
            return

        try:
            message, thread = await self.service.create_entry(
                interaction=interaction,
                category_key=self.category_key,
                title=self.title_input.value.strip(),
                summary=self.summary_input.value.strip(),
                tagged_user_ids=self.tagged_user_ids,
            )
        except RuntimeError as error:
            await safe_followup_send(interaction, f"❌ {error}", ephemeral=True)
            return

        if thread is None:
            await safe_followup_send(
                interaction,
                f"✅ Запись создана: {message.jump_url}\nДоказательства можно добавить следующим сообщением в архивный канал.",
                ephemeral=True,
            )
            return

        await safe_followup_send(
            interaction,
            (
                f"✅ Запись создана: {message.jump_url}\n"
                f"Сразу докиньте скрины, файлы или ссылки в тред: {thread.mention}"
            ),
            view=EvidenceThreadView(
                f"https://discord.com/channels/{thread.guild.id}/{thread.parent_id}/{thread.id}"
            ),
            ephemeral=True,
        )


class KompromatCategorySelect(Select):
    def __init__(self, service: KompromatService):
        self.service = service
        super().__init__(
            placeholder="Выберите категорию компромата",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=category.label,
                    value=category.key,
                    description=category.description,
                    emoji=category.emoji,
                )
                for category in service.categories()
            ],
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await safe_response_edit_message(
            interaction,
            content="Отметьте участников нарушения. Этот шаг можно пропустить.",
            view=KompromatParticipantsView(self.service, self.values[0]),
        )


class KompromatCategoryView(View):
    def __init__(self, service: KompromatService):
        super().__init__(timeout=120)
        self.add_item(KompromatCategorySelect(service))


class KompromatParticipantsSelect(UserSelect):
    def __init__(self, service: KompromatService, category_key: str):
        self.service = service
        self.category_key = category_key
        super().__init__(
            placeholder="Выберите участников нарушения",
            min_values=1,
            max_values=10,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        tagged_user_ids = [
            selected.id
            for selected in self.values
            if isinstance(selected, (discord.Member, discord.User))
        ]
        await safe_response_send_modal(
            interaction,
            KompromatCreateModal(self.service, self.category_key, tagged_user_ids),
        )


class KompromatParticipantsView(View):
    def __init__(self, service: KompromatService, category_key: str):
        super().__init__(timeout=120)
        self.service = service
        self.category_key = category_key

        self.add_item(KompromatParticipantsSelect(service, category_key))

        skip_button = Button(
            label="Продолжить без тегов",
            style=discord.ButtonStyle.secondary,
            emoji="➡️",
        )
        skip_button.callback = self._skip
        self.add_item(skip_button)

    async def _skip(self, interaction: discord.Interaction) -> None:
        await safe_response_send_modal(
            interaction,
            KompromatCreateModal(self.service, self.category_key, []),
        )


class KompromatSearchUserSelect(UserSelect):
    def __init__(self, service: KompromatService):
        self.service = service
        super().__init__(
            placeholder="Выберите игрока для поиска",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected_user = self.values[0]
        if not isinstance(selected_user, discord.Member) or interaction.guild is None:
            await safe_response_send_message(
                interaction,
                "❌ Не удалось определить участника.",
                ephemeral=True,
            )
            return

        entries = self.service.search_by_member(guild_id=interaction.guild.id, member=selected_user)
        embed = self.service.build_search_embed(member=selected_user, entries=entries)
        await safe_response_edit_message(
            interaction,
            content=None,
            embed=embed,
            view=KompromatSearchView(self.service),
        )


class KompromatSearchView(View):
    def __init__(self, service: KompromatService):
        super().__init__(timeout=120)
        self.add_item(KompromatSearchUserSelect(service))


class KompromatPanelView(View):
    def __init__(self, service: KompromatService):
        super().__init__(timeout=None)
        self.service = service

        create_button = Button(
            label="Добавить компромат",
            style=discord.ButtonStyle.danger,
            emoji="🗂️",
            custom_id="kompromat:create",
        )
        create_button.callback = self._open_create
        self.add_item(create_button)

        search_button = Button(
            label="Найти по игроку",
            style=discord.ButtonStyle.secondary,
            emoji="🔎",
            custom_id="kompromat:search",
        )
        search_button.callback = self._open_search
        self.add_item(search_button)

    async def _open_create(self, interaction: discord.Interaction) -> None:
        await safe_response_send_message(
            interaction,
            "Сначала выберите категорию, потом при необходимости отметьте участников, и после этого откроется форма.",
            view=KompromatCategoryView(self.service),
            ephemeral=True,
        )

    async def _open_search(self, interaction: discord.Interaction) -> None:
        await safe_response_send_message(
            interaction,
            "Выберите игрока, чтобы посмотреть записи с его тегом.",
            view=KompromatSearchView(self.service),
            ephemeral=True,
        )
