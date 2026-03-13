from __future__ import annotations

from dataclasses import dataclass

import discord

from .config import TicketGuildSettings, TicketsSettings

ROOT_PANEL = "root"
PANEL_SUPPORT = "support"
PANEL_FRACTION = "fraction"
PANEL_RP = "rp"

STATUS_OPEN = "open"
STATUS_IN_PROGRESS = "in_progress"
STATUS_WAITING_USER = "waiting_user"
STATUS_CLOSED = "closed"

STATUS_LABELS = {
    STATUS_OPEN: "Открыт",
    STATUS_IN_PROGRESS: "В работе",
    STATUS_WAITING_USER: "Ожидает игрока",
    STATUS_CLOSED: "Закрыт",
}


@dataclass(slots=True, frozen=True)
class TicketFieldSpec:
    key: str
    label: str
    placeholder: str
    style: discord.TextStyle = discord.TextStyle.short
    required: bool = True
    max_length: int = 400


@dataclass(slots=True, frozen=True)
class TicketTypeSpec:
    key: str
    panel_key: str
    label: str
    description: str
    emoji: str
    channel_prefix: str
    intro: str
    modal_title: str
    color_attr: str
    category_attr: str
    fields: tuple[TicketFieldSpec, ...]
    attachment_prompt: str | None = None

    def color(self, settings: TicketsSettings) -> int:
        return getattr(settings, self.color_attr)

    def category_id(self, settings: TicketGuildSettings) -> int:
        return getattr(settings, self.category_attr)


@dataclass(slots=True, frozen=True)
class PanelSpec:
    key: str
    label: str
    title: str
    description: str
    button_label: str
    button_emoji: str
    color_attr: str
    ticket_type_keys: tuple[str, ...]

    def color(self, settings: TicketsSettings) -> int:
        return getattr(settings, self.color_attr)


TICKET_TYPES = {
    "pass": TicketTypeSpec(
        key="pass",
        panel_key=PANEL_SUPPORT,
        label="Проходка",
        description="Вопросы по проходкам и доступам.",
        emoji="🎫",
        channel_prefix="pass",
        intro="Опишите вопрос по проходке как можно подробнее.",
        modal_title="Проходка",
        color_attr="main_color",
        category_attr="ticket_category_id",
        fields=(
            TicketFieldSpec("subject", "Тема", "Например: Не пускает на сервер", max_length=100),
            TicketFieldSpec(
                "details",
                "Подробности",
                "Что произошло, когда началась проблема и что вы уже пробовали.",
                style=discord.TextStyle.paragraph,
                max_length=1000,
            ),
        ),
    ),
    "report": TicketTypeSpec(
        key="report",
        panel_key=PANEL_SUPPORT,
        label="Жалоба на игрока",
        description="Жалоба на нарушение правил проекта.",
        emoji="📕",
        channel_prefix="report",
        intro="Укажите игрока, нарушение и приложите доказательства.",
        modal_title="Жалоба на игрока",
        color_attr="main_color",
        category_attr="ticket_category_id",
        fields=(
            TicketFieldSpec("player", "Игрок", "Ник игрока", max_length=64),
            TicketFieldSpec("rule", "Нарушение", "Какое правило было нарушено?", max_length=120),
            TicketFieldSpec(
                "evidence",
                "Доказательства",
                "Ссылки, скриншоты, видео и описание ситуации.",
                style=discord.TextStyle.paragraph,
                max_length=1000,
            ),
        ),
    ),
    "appeal": TicketTypeSpec(
        key="appeal",
        panel_key=PANEL_SUPPORT,
        label="Обжалование решения администрации",
        description="Апелляция на наказание или решение staff-команды.",
        emoji="⚖️",
        channel_prefix="appeal",
        intro="Опишите, что хотите обжаловать и почему.",
        modal_title="Апелляция",
        color_attr="main_color",
        category_attr="ticket_category_id",
        fields=(
            TicketFieldSpec("subject", "Что обжалуете", "Например: бан / мут / отклонение жалобы", max_length=120),
            TicketFieldSpec(
                "reason",
                "Почему считаете решение ошибочным",
                "Кратко и по фактам.",
                style=discord.TextStyle.paragraph,
                max_length=1000,
            ),
            TicketFieldSpec(
                "evidence",
                "Что приложить",
                "Ссылки, доказательства или дополнительные материалы.",
                style=discord.TextStyle.paragraph,
                required=False,
                max_length=1000,
            ),
        ),
    ),
    "bugs": TicketTypeSpec(
        key="bugs",
        panel_key=PANEL_SUPPORT,
        label="Баги и тех. проблемы",
        description="Сообщение о багах, недочетах и технических сбоях.",
        emoji="⚙️",
        channel_prefix="bug",
        intro="Опишите проблему так, чтобы ее можно было воспроизвести.",
        modal_title="Баг или тех. проблема",
        color_attr="main_color",
        category_attr="ticket_category_id",
        fields=(
            TicketFieldSpec("subject", "Где проблема", "Система, место или команда", max_length=120),
            TicketFieldSpec(
                "details",
                "Описание проблемы",
                "Что не работает, когда это заметили и что важно учесть.",
                style=discord.TextStyle.paragraph,
                max_length=1000,
            ),
        ),
    ),
    "other": TicketTypeSpec(
        key="other",
        panel_key=PANEL_SUPPORT,
        label="Другое",
        description="Прочие вопросы к команде проекта.",
        emoji="🪇",
        channel_prefix="other",
        intro="Напишите, чем мы можем помочь.",
        modal_title="Другое обращение",
        color_attr="main_color",
        category_attr="ticket_category_id",
        fields=(
            TicketFieldSpec("subject", "Тема", "Коротко опишите вопрос", max_length=120),
            TicketFieldSpec(
                "details",
                "Подробности",
                "Расскажите о запросе подробнее.",
                style=discord.TextStyle.paragraph,
                max_length=1000,
            ),
        ),
    ),
    "fraction_ad": TicketTypeSpec(
        key="fraction_ad",
        panel_key=PANEL_FRACTION,
        label="Реклама фракции",
        description="Заявка на рекламу фракции.",
        emoji="📢",
        channel_prefix="fraction-ad",
        intro="Заполните короткую анкету по вашей фракции.",
        modal_title="Реклама фракции",
        color_attr="fraction_color",
        category_attr="fraction_category_id",
        fields=(
            TicketFieldSpec("fraction_name", "Название фракции", "Как называется фракция?", max_length=100),
            TicketFieldSpec("contact", "Discord", "Укажите Discord для связи", max_length=100),
            TicketFieldSpec(
                "details",
                "Описание",
                "Кого ищете, чем занимаетесь, что важно указать в рекламе.",
                style=discord.TextStyle.paragraph,
                max_length=1000,
            ),
        ),
    ),
    "fraction_reg": TicketTypeSpec(
        key="fraction_reg",
        panel_key=PANEL_RP,
        label="Регистрация фракции",
        description="Официальная регистрация RP-фракции.",
        emoji="👑",
        channel_prefix="fraction-reg",
        intro="Заполните заявку на регистрацию фракции.",
        modal_title="Регистрация фракции",
        color_attr="rp_color",
        category_attr="rp_category_id",
        fields=(
            TicketFieldSpec("fraction_name", "Название фракции", "Полное название", max_length=100),
            TicketFieldSpec("leader", "Лидер", "Кто руководитель?", max_length=100),
            TicketFieldSpec(
                "concept",
                "Концепция",
                "Кратко опишите идею, состав и задачи фракции.",
                style=discord.TextStyle.paragraph,
                max_length=1000,
            ),
        ),
        attachment_prompt="Пожалуйста, прикрепите герб или знамя следующим сообщением в этот тикет.",
    ),
    "city_reg": TicketTypeSpec(
        key="city_reg",
        panel_key=PANEL_RP,
        label="Регистрация города",
        description="Регистрация города или поселения.",
        emoji="🏘️",
        channel_prefix="city-reg",
        intro="Заполните заявку на регистрацию города.",
        modal_title="Регистрация города",
        color_attr="rp_color",
        category_attr="rp_category_id",
        fields=(
            TicketFieldSpec("city_name", "Название города", "Как называется город?", max_length=100),
            TicketFieldSpec("location", "Локация", "Где он расположен?", max_length=100),
            TicketFieldSpec(
                "concept",
                "Концепция",
                "Опишите идею, законы и особенности поселения.",
                style=discord.TextStyle.paragraph,
                max_length=1000,
            ),
        ),
        attachment_prompt="Пожалуйста, прикрепите герб или знамя города следующим сообщением в этот тикет.",
    ),
    "rp_appeal": TicketTypeSpec(
        key="rp_appeal",
        panel_key=PANEL_RP,
        label="RP-обращение",
        description="Любой RP-вопрос, не попавший в другие категории.",
        emoji="🎭",
        channel_prefix="rp",
        intro="Опишите RP-вопрос или ситуацию.",
        modal_title="RP-обращение",
        color_attr="rp_color",
        category_attr="rp_category_id",
        fields=(
            TicketFieldSpec("subject", "Тема", "О чем обращение?", max_length=120),
            TicketFieldSpec(
                "details",
                "Подробности",
                "Напишите все важные детали.",
                style=discord.TextStyle.paragraph,
                max_length=1000,
            ),
        ),
    ),
}

ROOT_PANEL_SPEC = PanelSpec(
    key=ROOT_PANEL,
    label="Тикеты",
    title="🎫 Система тикетов",
    description=(
        "Выберите категорию обращения и заполните короткую форму.\n\n"
        "📌 После создания тикета staff увидит заявку и возьмет ее в работу."
    ),
    button_label="Создать тикет",
    button_emoji="🎫",
    color_attr="main_color",
    ticket_type_keys=tuple(TICKET_TYPES.keys()),
)

PANELS = {
    PANEL_SUPPORT: PanelSpec(
        key=PANEL_SUPPORT,
        label="Обращения",
        title="📝 Обращения",
        description=(
            "Для связи с командой проекта.\n\n"
            "📌 Выберите тип обращения и заполните короткую форму.\n"
            "⏰ После создания тикета staff увидит ваш запрос и возьмет его в работу."
        ),
        button_label="Создать обращение",
        button_emoji="📝",
        color_attr="main_color",
        ticket_type_keys=("pass", "report", "appeal", "bugs", "other"),
    ),
    PANEL_FRACTION: PanelSpec(
        key=PANEL_FRACTION,
        label="Реклама фракций",
        title="📢 Реклама фракций",
        description=(
            "Для подачи заявки на рекламу вашей фракции.\n\n"
            "📌 Нажмите кнопку и заполните анкету.\n"
            "⏰ Staff проверит заявку и ответит в тикете."
        ),
        button_label="Подать заявку",
        button_emoji="📢",
        color_attr="fraction_color",
        ticket_type_keys=("fraction_ad",),
    ),
    PANEL_RP: PanelSpec(
        key=PANEL_RP,
        label="RP-обращения",
        title="🎭 RP-обращения",
        description=(
            "Для регистрации города, фракции и решения RP-вопросов.\n\n"
            "📌 Выберите нужный тип обращения и заполните форму.\n"
            "⏰ Чем точнее заявка, тем быстрее ее можно обработать."
        ),
        button_label="Создать RP-тикет",
        button_emoji="🎭",
        color_attr="rp_color",
        ticket_type_keys=("fraction_reg", "city_reg", "rp_appeal"),
    ),
}


def get_panel(panel_key: str) -> PanelSpec:
    if panel_key == ROOT_PANEL:
        return ROOT_PANEL_SPEC
    return PANELS[panel_key]


def get_ticket_type(ticket_type_key: str) -> TicketTypeSpec:
    return TICKET_TYPES[ticket_type_key]


def iter_panels() -> list[PanelSpec]:
    return list(PANELS.values())


def iter_ticket_types(panel_key: str) -> list[TicketTypeSpec]:
    panel = get_panel(panel_key)
    return [TICKET_TYPES[ticket_type_key] for ticket_type_key in panel.ticket_type_keys]


def get_status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)
