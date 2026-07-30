from __future__ import annotations

import hashlib
import re
import unicodedata


ONBOARDING_CHANNEL_ID = 1343124803858599977
EMBED_COLOR = 0x831818
BANNER_FILENAME_TEMPLATE = "greeting_{member_id}.png"

THEMES = (
    "городская повседневность и ворота",
    "ремесленные мастерские и цеховая жизнь",
    "дорога, обозы и постоялый двор",
    "рынок, торговля и городские слухи",
    "ратуша, писари и городские реестры",
    "пристань, путешествия и новые собеседники",
    "дипломатия и спокойная ирония",
)

FALLBACK_LINES = (
    "В городском реестре появилось новое имя, и ворота снова открыты.",
    "На постоялом дворе сегодня стало немного люднее.",
    "Писарь освободил строку в реестре и приготовил свежие чернила.",
    "Колокол у ворот сегодня прозвучал ещё для одного гостя.",
    "В трактире уже спорят, кто первым предложит новому гостю работу.",
    "Караван задержался у ворот ровно настолько, чтобы принять нового спутника.",
    "У городских ворот прибавилось голосов и стало чуть оживлённее.",
    "На рыночной площади как раз не хватало ещё одного собеседника.",
    "Местный хронист обещал не приукрашивать это прибытие. Пока что.",
    "Кто-то в ратуше уже ищет свободный стул для нового участника.",
    "Печать на пропуске поставлена, ворота открыты.",
    "Новое имя внесено в список жителей без канцелярской волокиты.",
    "У пристани появился ещё один человек, которому явно есть что рассказать.",
    "Кузнец не отвлёкся от работы, зато трактирщик уже заметил гостя.",
    "Город встретил нового жителя обычным шумом мастерских и рынка.",
    "На карте мира пока ничего не изменилось, но день только начался.",
)

_FORBIDDEN_PHRASES = (
    "тебе суждено",
    "вершить историю",
    "новая глава истории",
    "судьба привела",
    "легенда начинается",
    "великие свершения",
    "эпическое приключение",
    "добро пожаловать, путник",
)
_PREFIX_PATTERN = re.compile(r"^(?:реплика|ответ|фраза)\s*:\s*", re.IGNORECASE)
_WORD_PATTERN = re.compile(r"[\wЁёА-Яа-я-]+", re.UNICODE)


def fallback_line(member_id: int) -> str:
    digest = hashlib.sha256(str(member_id).encode("ascii")).digest()
    return FALLBACK_LINES[int.from_bytes(digest[:4], "big") % len(FALLBACK_LINES)]


def theme_for(member_id: int) -> str:
    digest = hashlib.sha256(f"theme:{member_id}".encode("ascii")).digest()
    return THEMES[int.from_bytes(digest[:4], "big") % len(THEMES)]


def sanitize_generated_line(raw_line: str) -> str | None:
    line = _PREFIX_PATTERN.sub("", " ".join(raw_line.split())).strip(' "“”«»')
    folded = line.casefold()
    words = _WORD_PATTERN.findall(line)

    if not 20 <= len(line) <= 180 or not 4 <= len(words) <= 22:
        return None
    if any(phrase in folded for phrase in _FORBIDDEN_PHRASES):
        return None
    if any(marker in folded for marker in ("http://", "https://", "discord.gg", "<@", "<#")):
        return None
    if any(marker in line for marker in ("@", "`", "**", "__", "||")):
        return None
    if any(unicodedata.category(character) in {"Cc", "Cs"} for character in line):
        return None
    if not any("а" <= character.casefold() <= "я" or character.casefold() == "ё" for character in line):
        return None

    return line if line.endswith((".", "!", "?")) else f"{line}."


def build_embed_description(*, member_mention: str, line: str) -> str:
    return (
        f"## Добро пожаловать, {member_mention}!\n\n"
        f"*{line}*\n\n"
        "Познакомиться с проектом и узнать, с чего начать, можно в "
        f"<#{ONBOARDING_CHANNEL_ID}>."
    )
