# Warlords Discord Bot

Модульный Discord-бот проекта Warlords. В репозитории остаются только функции,
которые действительно используются сервером:

- тикеты;
- welcome-панель;
- правила;
- выдача ролей;
- ручной архив компромата;
- presence;
- безопасный запуск обновления из Discord.

Старые DiscordAuth, AI-автоответчик, AI-модератор и веб-админка удалены.
Нейтральный AI-клиент сохранён в `src/integrations/ai` для будущих прикладных
сценариев, но сам по себе он не читает сообщения и ничего не модерирует.

## Структура

```text
Warlords-bot/
├── assets/                  изображения и шрифты Discord-панелей
├── deploy/                  systemd units и атомарный deployment
├── src/
│   ├── bot.py               точка входа
│   ├── core/                bootstrap и общий runtime панелей
│   ├── integrations/ai/     независимый OpenAI-compatible клиент
│   └── modules/             пользовательские функции бота
├── tests/                   unit-тесты
└── requirements.txt
```

Поддерживаемые модули явно перечислены в `src/modules/__init__.py`. Случайный
пакет больше не будет автоматически загружен как модуль.

## Локальный запуск

Требуется Python 3.11 или новее.

```bash
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item src/.env.example src/.env
.\.venv\Scripts\python.exe src/bot.py
```

Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
cp src/.env.example src/.env
.venv/bin/python src/bot.py
```

Локальный `src/.env` опционален. В production переменные передаются через
`/etc/warlords-bot.env` и имеют приоритет.

## Конфигурация

- `DISCORD_TOKEN` — обязательный токен бота.
- `APP_COMMAND_GUILD_ID` — тестовый Discord-сервер для быстрой синхронизации
  slash-команд; без него команды глобальные.
- `ENABLED_MODULES` — необязательный список модулей. По умолчанию включены все
  поддерживаемые модули.
- `BOT_UPDATE_ALLOWED_USER_IDS` — Discord ID владельцев, которым разрешена
  команда `/bot update`. Права администратора сервера всё равно обязательны.

Настройки тикетов и опубликованных панелей хранятся в SQLite, а не в `.env`.

## AI-интеграция

`OpenAiCompatibleClient` является инфраструктурным адаптером без Discord-логики.
Он поддерживает обычные chat-completions endpoints:

- `AI_BASE_URL`;
- `AI_MODEL`;
- `AI_API_KEY` — опционален для локального endpoint;
- `AI_TIMEOUT_SECONDS` — по умолчанию `30`;
- `AI_MAX_RESPONSE_BYTES` — по умолчанию `1000000`.

Удалённые endpoints обязаны использовать HTTPS. HTTP разрешён только для
loopback-адресов.

## Production

Production не обновляет живой Git-worktree. `/bot update` может только создать
фиксированный файл-заявку в state-каталоге. Root-owned `systemd.path` запускает
`warlords-bot-deploy.service`. Деплой:

1. клонирует заданную ветку в новый release-каталог;
2. создаёт отдельную virtualenv и ставит зависимости;
3. запускает все тесты и компиляцию;
4. атомарно переключает `current` symlink;
5. перезапускает бота;
6. возвращает предыдущий release, если новый процесс не остаётся активным.

Подробная установка описана в `deploy/README.md`.

## Проверки

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

Основные SQLite-файлы:

- `data/tickets.sqlite3`;
- `data/kompromat.sqlite3`;
- `data/panel_registry.sqlite3`.

`panel_registry.sqlite3` нужен обычным Discord-панелям и не относится к
удалённой веб-админке.
