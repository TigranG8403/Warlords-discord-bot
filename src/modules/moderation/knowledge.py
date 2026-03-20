from __future__ import annotations

from .config import ModerationKnownProfile


DEFAULT_SERVER_RULES = (
    "Запрещены жёсткие личные оскорбления, наезды на религии и на сам Warlords.",
    "Обычный мат без личного наезда автомод сам по себе не трогает.",
    "Реклама и внешние промо-ссылки автоматически не караются: бот зовёт модерацию.",
    "Казино, фишинг и явный скам считаются тяжёлым нарушением.",
    "Спам, флуд и бессмысленные массовые пинги запрещены.",
)

CORE_SERVER_FACTS = (
    "Warlords — масштабный проект в сеттинге средневековья, где игроки создают государства, плетут интриги, торгуют, возводят города и замки, ведут войны и вписывают своё имя в историю.",
)

CHANNEL_FACTS = (
    "Информация о сервере находится в канале <#1343124803858599977>.",
    "Правила Discord-сервера находятся в канале <#1343124661474426932>.",
    "Выбрать дополнительные роли можно в канале <#1350444070991822898>.",
    "Тикеты открываются через канал <#1426228872105693306>.",
    "Привязать ник можно в канале <#1439303883334746192>.",
)

LAUNCH_AND_PROJECT_FACTS = (
    "Сервер сейчас разрабатывается и откроется в ближайшее время на версии 1.20.1 Forge на сборке бетатеста.",
    "Laurel of Ages — долгостройный, более проработанный проект на NeoForge 1.21.1 под руководством мессира и Малезиаса.",
    "Фраза «сервер завтра в 3» — локальный мем про открытие; она уместна только когда прямо спрашивают о времени, дате или старте сервера.",
)

RELATED_PROJECT_FACTS = (
    "Варферия, она же Warfare или Minecraft Warfare, — дружеский к Warlords сервер схожей тематики.",
    "Minecraft Warfare — масштабный исторический полит-RP сервер в Minecraft, где игроки создают цивилизации, проходят эпохи от Бронзового века и Античности до Средневековья и Нового времени, собирают армии и участвуют в войнах.",
    "Вики Варферии находится по адресу https://minecraft-warferia.fandom.com/ru/wiki/Заглавная.",
)

MOD_FACTS = (
    "Рекруты — мод на НПС-солдат, одна из основ серверов по типу Warlords и Warferia.",
)

SOFT_ESCALATION_FACTS = (
    "Если в чате сыплются оскорбления или кринж, но до мута или админ-эскалации ещё не дошло, можно звать Почему (<@844973616952639508>).",
)

DEFAULT_SERVER_FACTS = CORE_SERVER_FACTS + CHANNEL_FACTS
EXTRA_SERVER_FACTS = LAUNCH_AND_PROJECT_FACTS + RELATED_PROJECT_FACTS + MOD_FACTS

CORE_KNOWN_PROFILES = (
    ModerationKnownProfile(
        discord_id=1034533546863382649,
        primary_name="messire",
        aliases=("mss1r", "мессир"),
        summary=(
            "создатель и разработчик бота; делает много модов, мало говорит, "
            "но в своей компании может вести себя раскрепощённо и с матом"
        ),
    ),
    ModerationKnownProfile(
        discord_id=557814715913469976,
        primary_name="Jamb1",
        aliases=("Джамби",),
        summary="создатель сервера; обеспеченный человек, любит европку и кс, активен не слишком часто",
    ),
    ModerationKnownProfile(
        discord_id=710800410587299872,
        primary_name="Tigran",
        aliases=("TigranG8403", "Тигран"),
        summary="сосоздатель бота; умный и скромный человек",
    ),
    ModerationKnownProfile(
        discord_id=586199885343096833,
        primary_name="Малезиас",
        aliases=("падишах император",),
        summary="сильный гуманитарий; любит политику и военполит-игры вроде хойки и европки",
    ),
)

COMMUNITY_KNOWN_PROFILES = (
    ModerationKnownProfile(
        discord_id=844973616952639508,
        primary_name="Почему",
        aliases=(),
        summary="старший модератор Discord; строгий, но справедливый, коллега по модерации",
    ),
)

RELATED_PROJECT_PROFILES = (
    ModerationKnownProfile(
        discord_id=451031568895705109,
        primary_name="Vanius",
        aliases=("Иван",),
        summary="владелец Minecraft Warfare",
    ),
    ModerationKnownProfile(
        discord_id=761296747715624960,
        primary_name="Uze",
        aliases=(),
        summary="администратор и игрок Варферии",
    ),
    ModerationKnownProfile(
        discord_id=745608321435959318,
        primary_name="FemoDeBenj",
        aliases=("Фемыч",),
        summary="админ и разработчик Варферии",
    ),
    ModerationKnownProfile(
        discord_id=238399235744071680,
        primary_name="talhanation",
        aliases=(),
        summary="создатель и разработчик мода Рекруты",
    ),
    ModerationKnownProfile(
        discord_id=389098582604775436,
        primary_name="Roman Kaiser",
        aliases=("Ярс",),
        summary="разработчик мода Рекруты, также разработчик Варферии",
    ),
)

SEEDED_KNOWN_PROFILES = CORE_KNOWN_PROFILES
EXTRA_KNOWN_PROFILES = COMMUNITY_KNOWN_PROFILES + RELATED_PROJECT_PROFILES
