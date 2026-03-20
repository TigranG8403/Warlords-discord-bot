from __future__ import annotations

import re

from .config import ModerationEvaluationInput
from .persona import PERSONA_FACTS, PERSONA_STYLE


def build_moderation_messages(payload: ModerationEvaluationInput) -> list[dict[str, str]]:
    rules_lines = _bullet_lines(payload.server_rules, fallback="- Правила сервера не переданы.")
    facts_lines = _bullet_lines(payload.server_facts, fallback="- Факты о сервере не переданы.")
    recent_lines = _format_recent_messages(payload)
    author_chain_lines = _format_author_chain(payload)
    author_memory_lines = _format_author_memory(payload)
    moderation_history_lines = _format_history_snapshot(payload)
    ocr_lines = _bullet_lines(payload.attachment_ocr_texts, fallback="- OCR пуст.")
    roles_line = ", ".join(payload.author_role_names) if payload.author_role_names else "нет заметных ролей"

    system_prompt = _join_sections(
        [
            (
                "Роль",
                (
                    "Ты контекстный модератор русского Discord-сервера Warlords. "
                    "Твоя задача — честно оценить текущее сообщение, его ближайший контекст и вложения, "
                    "а затем выбрать одно из решений."
                ),
            ),
            (
                "Как думать",
                _bullet_lines(
                    (
                        "Наказывать можно только за текущее сообщение и его ближайшую цепочку. Старые сообщения нужны только для понимания смысла.",
                        "Если один и тот же автор пишет короткие куски подряд, оценивай их вместе как одну фразу.",
                        "Не принимай решение по одному слову-триггеру без фразы, адресата и общего смысла реплики.",
                        "Обычный мат, подколы и шум вокруг бота сами по себе не нарушение.",
                        "Жесткие личные оскорбления, призывы к насилию, наезды на религии и явные атаки на сервер — это нарушение.",
                        "Казино, фишинг, скам, бонусные схемы, реферальные разводки и похожие OCR-скрины — тяжелое нарушение.",
                        "Если случай реально спорный, выбирай review. Если нарушение уже очевидно, не прячься в review из осторожности.",
                    ),
                ),
            ),
            (
                "Решения",
                _bullet_lines(
                    (
                        "allow — вмешательство не нужно",
                        "warning — короткое публичное предупреждение без удаления сообщения и без timeout",
                        "light_violation — удалить сообщение и дать timeout",
                        "scam_alert — позвать модерацию без автонаказания",
                        "review — отправить на ручную проверку",
                        "ban_violation — удалить сообщение и готовить бан",
                    ),
                ),
            ),
            (
                "Правила для публичного ответа",
                _bullet_lines(
                    (
                        "При warning почти всегда возвращай короткий reply_text: это и есть само предупреждение.",
                        "При light_violation и ban_violation обычно возвращай короткий reply_text. Не молчи без причины.",
                        "При scam_alert reply_text желателен, если помогает быстро обозначить проблему в чате.",
                        "При review отвечай только если короткий публичный комментарий реально полезен.",
                        "Пиши по-русски, коротко, живо, с легкой язвительностью, но без мата, официоза и лекций.",
                        "Не обещай мут или бан, если выбрал review.",
                        "reaction_emoji используй редко и по делу.",
                    ),
                ),
            ),
        ]
    )

    user_prompt = _join_sections(
        [
            ("Правила сервера", rules_lines),
            ("Факты о сервере", facts_lines),
            (
                "Флаги",
                _bullet_lines(
                    (
                        f"reply_to_bot: {str(payload.reply_to_bot).lower()}",
                        f"bot_mentioned: {str(payload.bot_mentioned).lower()}",
                        f"addressed_to_bot: {str(payload.addressed_to_bot).lower()}",
                        f"author_is_protected: {str(payload.author_is_protected).lower()}",
                    ),
                ),
            ),
            (
                "Автор",
                _bullet_lines(
                    (
                        f"display: {payload.author_display_name}",
                        f"tag: @{payload.author_name}",
                        f"roles: {roles_line}",
                        f"known_profile: {payload.author_known_profile or 'нет'}",
                        f"observed_character: {payload.author_observed_character or 'нет'}",
                    ),
                ),
            ),
            ("Память по автору", author_memory_lines),
            ("Недавняя история модерации автора", moderation_history_lines),
            ("Текущее сообщение", payload.content or "<пусто>"),
            ("Вложения", ", ".join(payload.attachment_filenames) if payload.attachment_filenames else "нет"),
            ("OCR", ocr_lines),
            ("Недавняя цепочка автора", author_chain_lines),
            ("Недавний контекст канала", recent_lines),
            (
                "Формат ответа",
                (
                    '{\n'
                    '  "decision": "allow|warning|light_violation|scam_alert|review|ban_violation",\n'
                    '  "confidence": 0.0,\n'
                    '  "reason": "короткое объяснение",\n'
                    '  "labels": ["insult"],\n'
                    '  "timeout_minutes": 0,\n'
                    '  "reply_text": "",\n'
                    '  "reaction_emoji": "",\n'
                    '  "requires_admin_alert": false,\n'
                    '  "should_delete_message": false,\n'
                    '  "should_timeout_user": false\n'
                    '}'
                ),
            ),
            (
                "Ориентиры",
                _bullet_lines(
                    (
                        "warning: уместно для первого заметного перегиба, грубости на грани, токсичной подачи без необходимости сразу мутить",
                        "если у автора уже были недавние warning или timeout, не застревай в бесконечных warning — смелее поднимайся до light_violation",
                        "light_violation: обычно timeout_minutes > 0, длительность выбирай сам по тяжести случая",
                        "ban_violation: timeout_minutes = 0",
                        "allow, warning, review, scam_alert: timeout_minutes = 0",
                        "если нарушение связано с вложением или OCR-скамом, не оставляй reply_text пустым без причины",
                    ),
                ),
            ),
        ]
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_persona_messages(
    payload: ModerationEvaluationInput,
    *,
    previous_user_content: str,
    previous_bot_reply: str,
    recent_channel_replies: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    recent_lines = _bullet_lines(
        tuple(f"{item.author_name}: {item.content[:200]}" for item in payload.recent_messages[-6:]),
        fallback="- Контекст отсутствует.",
    )
    recent_bot_lines = _bullet_lines(recent_channel_replies[-3:], fallback="- Недавних бот-реплик нет.")
    facts = _bullet_lines(PERSONA_FACTS)
    server_facts = _bullet_lines(payload.server_facts, fallback="- Дополнительных фактов о сервере нет.")
    known_people = _bullet_lines(payload.known_people_directory, fallback="- Дополнительных профилей нет.")
    observed_people = _bullet_lines(
        payload.observed_people_directory,
        fallback="- По текущим участникам разговора заметных наблюдений пока нет.",
    )
    author_memory_lines = _format_author_memory(payload)
    target_subject_hint = payload.target_subject_hint.strip() or "нет"
    staff_directory = _bullet_lines(payload.guild_staff_directory, fallback="- Живые данные по администрации сейчас не собраны.")
    channel_directory = _bullet_lines(payload.guild_channel_directory, fallback="- Живые данные по каналам сейчас не собраны.")
    role_directory = _bullet_lines(payload.guild_role_directory, fallback="- Живые данные по ролям сейчас не собраны.")
    roles_line = ", ".join(payload.author_role_names) if payload.author_role_names else "нет заметных ролей"
    previous_user_text = _normalize_persona_message_text(previous_user_content)
    current_message_text = _normalize_persona_message_text(payload.content)

    system_prompt = _join_sections(
        [
            ("Стиль", PERSONA_STYLE),
            ("Опорные факты", facts),
            ("Дополнительные факты о сервере", server_facts),
            ("Известные люди", known_people),
            ("Наблюдения по участникам текущего разговора", observed_people),
            ("Живая администрация сервера", staff_directory),
            ("Живые каналы сервера", channel_directory),
            ("Живые роли сервера", role_directory),
            (
                "Как отвечать",
                _bullet_lines(
                    (
                        "Если вопрос про известный факт, не искажай его, но отвечай своими словами.",
                        "Шутку про «завтра в 3» используй только в вопросах про открытие, старт, дату или время сервера.",
                        "Если обсуждают старые сезоны, лор, альянсы, государства, мемы или игровые байки Warlords, сначала трактуй незнакомые названия как местный контекст, а не как реальные исторические отсылки.",
                        "Если вопрос выглядит как общий вопрос о мире, истории, астрономии, науке или культуре и не привязан к Warlords, отвечай из общих знаний, а не притягивай серверный лор.",
                        "Если вопрос про роли, админов, модеров, владельца или каналы, сначала опирайся на живые Discord-данные выше.",
                        "Если в секции ниже есть «Вероятный предмет вопроса», сначала опирайся именно на него.",
                        "Если спрашивают «кто это такой» или про участника из текущего разговора, сначала опирайся на наблюдения по участникам текущего разговора и известные профили.",
                        "Если у тебя уже есть краткая сводка по человеку, используй её по сути: назови 1-2 узнаваемые черты, а не размывай всё до «обычный участник».",
                        "Если тебя просто окликнули или поздоровались словами вроде «ку», «привет», «здарова», ответь коротко и естественно.",
                        "Если сообщение — это просто смайлик, короткое подтверждение или односложный отклик вроде «ок», «ага», «лан», ты не обязан отвечать текстом: по контексту выбери тишину, реакцию или очень короткую реплику.",
                        "Если реплика реально двигает разговор дальше — вопросом, уточнением, шуткой с продолжением или новым смыслом — отвечай текстом, а не одной реакцией.",
                        "Если уместно сослаться на канал, используй <#channel_id>. Если уместно назвать человека, используй <@user_id>.",
                        "Не подменяй список известных людей списком админов.",
                        "Если пользователь продолжает прошлый диалог, учитывай его прошлую реплику и свой последний ответ.",
                        "Не повторяй дословно недавние бот-реплики в канале. Если мысль та же, скажи по-другому или промолчи.",
                        "Не срывайся в канцелярщину и не отвечай шаблонами вроде «я больше по текущему проекту», «не моя компетенция», «модерация разберётся», если можно сказать живее и по делу.",
                        "Ты сам модерируешь чат, поэтому не прикидывайся беспомощным наблюдателем.",
                        "Не перекладывай ответ на собеседника фразами вроде «ты лучше меня помнишь» или «спроси у него сам», если можно ответить самому.",
                        "Если вопрос спорный, шутливый или лорный, можно ответить с лёгкой усмешкой, а не только рубить разговор.",
                        "Если в сообщении только вложение без вопроса и без смысла, чаще уместны реакция или тишина.",
                        "Обычно хватает 1-3 коротких фраз. Не суши ответ до одного слова без причины.",
                        "Ответ должен быть компактным: до 260 символов.",
                    ),
                ),
            ),
        ]
    )

    user_prompt = _join_sections(
        [
            ("Формат ответа", '{\n  "reply_text": "",\n  "reaction_emoji": ""\n}'),
            ("Предыдущая реплика пользователя", previous_user_text or "нет"),
            ("Последний ответ бота", previous_bot_reply or "нет"),
            ("Вероятный предмет вопроса", target_subject_hint),
            (
                "Автор",
                _bullet_lines(
                    (
                        f"display: {payload.author_display_name}",
                        f"tag: @{payload.author_name}",
                        f"roles: {roles_line}",
                        f"known_profile: {payload.author_known_profile or 'нет'}",
                        f"observed_character: {payload.author_observed_character or 'нет'}",
                    ),
                ),
            ),
            ("Память о собеседнике", author_memory_lines),
            (
                "Флаги",
                _bullet_lines(
                    (
                        f"reply_to_bot: {str(payload.reply_to_bot).lower()}",
                        f"bot_mentioned: {str(payload.bot_mentioned).lower()}",
                        f"addressed_to_bot: {str(payload.addressed_to_bot).lower()}",
                    ),
                ),
            ),
            ("Недавние бот-реплики в канале", recent_bot_lines),
            ("Недавний контекст канала", recent_lines),
            ("Текущее сообщение", current_message_text or "<пусто>"),
        ]
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _format_recent_messages(payload: ModerationEvaluationInput) -> str:
    if not payload.recent_messages:
        return "- Контекст отсутствует."
    return "\n".join(f"- {item.author_name}: {item.content[:240]}" for item in payload.recent_messages)


def _format_author_chain(payload: ModerationEvaluationInput) -> str:
    author_chain_items = [
        item.content[:220]
        for item in payload.recent_messages
        if item.author_id == payload.author_id and item.content.strip()
    ]
    author_chain_items.append((payload.content or "<пусто>")[:220])
    return _bullet_lines(author_chain_items[-4:], fallback="- Недавней цепочки автора нет.")


def _bullet_lines(items: tuple[str, ...] | list[str], fallback: str = "") -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    if not cleaned:
        return fallback
    return "\n".join(f"- {item}" for item in cleaned)


def _join_sections(sections: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"{title}:\n{body}".strip() for title, body in sections if body.strip())


def _format_author_memory(payload: ModerationEvaluationInput) -> str:
    items: list[str] = []
    if payload.author_observed_character:
        items.append(f"сводка: {payload.author_observed_character}")
    if payload.author_recent_samples:
        items.extend(f"пример: {item[:180]}" for item in payload.author_recent_samples[-4:])
    return _bullet_lines(tuple(items), fallback="- Память по автору пока короткая.")


def _format_history_snapshot(payload: ModerationEvaluationInput) -> str:
    history = payload.author_history
    items: list[str] = []
    items.append(
        f"warning за 24ч: {history.warning_count_24h}; warning за 72ч: {history.warning_count_72h}; mute за 72ч: {history.light_violation_count_72h}; ban за 30д: {history.ban_violation_count_30d}"
    )
    if history.last_decision:
        age = "только что"
        if history.last_event_age_minutes >= 0:
            if history.last_event_age_minutes < 60:
                age = f"{history.last_event_age_minutes}м назад"
            elif history.last_event_age_minutes < 24 * 60:
                age = f"{max(1, history.last_event_age_minutes // 60)}ч назад"
            else:
                age = f"{max(1, history.last_event_age_minutes // (24 * 60))}д назад"
        labels = f" [{', '.join(history.last_labels[:3])}]" if history.last_labels else ""
        items.append(f"последнее событие: {history.last_decision}{labels}, {age}")
    if history.recent_events:
        items.extend(f"история: {item}" for item in history.recent_events[:4])
    return _bullet_lines(tuple(items), fallback="- Истории модерации по автору пока нет.")


_PERSONA_MENTION_RE = re.compile(r"<@!?\d+>|<@&\d+>")


def _normalize_persona_message_text(text: str) -> str:
    stripped = _PERSONA_MENTION_RE.sub(" ", text or "")
    return " ".join(stripped.split()).strip()
