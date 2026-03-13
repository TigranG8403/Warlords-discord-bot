# Warlords Discord Bot

Внутренняя справка по текущей структуре проекта, конфигурации, runtime и тестам.

## Структура проекта

```text
Warlords-discord-bot/
├── assets/      статические изображения и шрифты для панелей
├── data/        SQLite-базы и служебные файлы состояния
├── src/
│   ├── bot.py   точка входа
│   ├── core/    общий runtime, bootstrap и утилиты
│   └── modules/ функциональные модули бота
├── tests/       unit-тесты
├── requirements.txt
└── README.md
```

В `src/modules/` находятся модули:

- `tickets`
- `welcome`
- `rules`
- `roles`
- `kompromat`
- `presence`

## Конфигурация

Базовая конфигурация читается из `src/.env`.

Обязательные и используемые переменные окружения:

- `DISCORD_TOKEN`
- `APP_COMMAND_GUILD_ID`
- `ENABLED_MODULES`

Настройки модуля `tickets` на уровне сервера хранятся в SQLite, в таблице `guild_settings` базы `data/tickets.sqlite3`.
Администратор управляет ими через slash-команды:

- `/tickets settings set`
- `/tickets settings show`
- `/tickets settings validate`

Там же хранится cooldown вызова staff.

Периоды суток для баннеров и обновления панелей считаются по часовому поясу `Europe/Moscow`.

## Запуск и bootstrap

- `src/bot.py` создаёт `WarlordsBot`, настраивает intents и логирование, загружает `src/.env` и синхронизирует slash-команды.
- `src/modules/__init__.py` либо поднимает все пакеты из `src/modules`, либо только те, что перечислены в `ENABLED_MODULES`.
- Каждый модуль должен экспортировать `build_module()`, который возвращает `BotModule` из `src/core/module.py`.
- `src/core/bootstrap.py` вызывает у модулей `register()`, регистрирует persistent views и затем вызывает `on_ready()`.
- Для ответов на interactions используется `src/core/discord_interactions.py`.

Запускать бота из корня репозитория можно так:

```bash
py -3 src/bot.py
```

## Установка на Ubuntu

Ниже базовый сценарий для Ubuntu 22.04/24.04 с запуском через `systemd`.

### 1. Подготовить сервер

Установить системные пакеты:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

### 2. Склонировать репозиторий и установить зависимости

```bash
cd /opt
sudo git clone https://github.com/TigranG8403/Warlords-multipurpose-bot
sudo chown -R $USER:$USER /opt/Warlords-multipurpose-bot
cd /opt/Warlords-multipurpose-bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Заполнить `src/.env`

Создать или отредактировать файл `src/.env`:

```env
DISCORD_TOKEN=...
APP_COMMAND_GUILD_ID=...
ENABLED_MODULES=tickets,welcome,rules,roles,kompromat,presence
```

Если нужен глобальный sync slash-команд, `APP_COMMAND_GUILD_ID` можно не указывать.

Настройки `tickets` на уровне сервера в `.env` не задаются. Их администратор настраивает в Discord через `/tickets settings set`.

### 4. Проверить ручной запуск

Из корня проекта:

```bash
cd /opt/Warlords-multipurpose-bot
source .venv/bin/activate
python src/bot.py
```

Если бот стартовал без ошибок, его можно остановить и перевести в `systemd`.

### 5. Создать `systemd`-сервис

Создать файл `/etc/systemd/system/warlords-bot.service`:

```ini
[Unit]
Description=Warlords Discord Bot
After=network.target

[Service]
Type=simple
User=<USER>
WorkingDirectory=/opt/Warlords-multipurpose-bot
ExecStart=/opt/Warlords-multipurpose-bot/.venv/bin/python src/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

После этого применить сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now warlords-bot
sudo systemctl status warlords-bot
```

Просмотр логов:

```bash
journalctl -u warlords-bot -f
```

### 6. Обновление бота на Ubuntu

```bash
cd /opt/Warlords-multipurpose-bot
git pull
source .venv/bin/activate
python -m pip install -r requirements.txt
sudo systemctl restart warlords-bot
```

### 7. Что важно на сервере

- каталог `data/` должен быть доступен на запись, потому что там создаются и обновляются SQLite-базы;
- после первого запуска slash-команды могут синхронизироваться не мгновенно;
- для тестового сервера удобнее задавать `APP_COMMAND_GUILD_ID`, чтобы команды появлялись быстрее.

## Общий runtime панелей

`src/core/panel_runtime.py` отвечает за публикацию и обновление панелей.

Что делает runtime:

- публикует panel message;
- хранит связь между сообщением панели и её записью в реестре;
- при старте перечитывает зарегистрированные панели и обновляет их;
- раз в минуту проверяет смену периода суток и обновляет панели только при необходимости;
- очищает реестр, если сообщение панели или канал были удалены.

Реестр опубликованных панелей хранится в:

- `data/panel_registry.sqlite3`

Для `welcome`, `rules`, `tickets` и `kompromat` в реестре хранится запись с `channel_id`.
Для `roles` там же хранится и конфигурация опубликованной role-панели.

## Карта модулей

- `tickets` - тикетная система с публичной панелью, созданием каналов, workflow staff, transcript, логами и DM пользователю.
- `welcome` - welcome-панель с публикацией через `/welcome panel`.
- `rules` - панель правил с публикацией через `/rules panel`.
- `roles` - панель выбора ролей через `/roles panel` и обработчики `on_raw_reaction_add` / `on_raw_reaction_remove`.
- `kompromat` - панель архива через `/kompromat panel`, поиск через `/kompromat search` и отдельные thread-доказательства.
- `presence` - обновление presence при запуске по общему числу участников на серверах.

## Как устроен `tickets`

Основные файлы:

- `src/modules/tickets/module.py` - slash-команды `/tickets panel` и `/tickets settings ...`, создание `PanelRuntime`, регистрация persistent views.
- `src/modules/tickets/service.py` - оркестрация: создание тикета, смена статусов, staff-права, закрытие, валидация guild settings.
- `src/modules/tickets/channel_ops.py` - имя канала, slug, permission overwrites, создание и удаление канала.
- `src/modules/tickets/repository.py` - SQLite-состояние тикетов и `guild_settings`, включая cooldown вызова staff.
- `src/modules/tickets/renderers.py` - embed'ы тикета, текстовые представления и transcript.
- `src/modules/tickets/notifications.py` - сообщения в staff-лог и DM пользователю.
- `src/modules/tickets/catalog.py` - типы тикетов, панели и метаданные.
- `src/modules/tickets/views/menus.py` - внешняя панель и modal-форма.
- `src/modules/tickets/views/inside.py` - кнопки внутри тикета: claim, waiting, call staff, close.

Жизненный цикл тикета:

1. Администратор сохраняет настройки сервера через `/tickets settings set`.
2. Администратор публикует панель через `/tickets panel`.
3. Пользователь открывает panel view и отправляет modal.
4. `TicketService.create_ticket()` валидирует ввод, настройки сервера и проверяет, нет ли уже активного тикета того же типа.
5. `channel_ops` создаёт канал, а `repository.py` записывает тикет в SQLite.
6. В канал отправляется control message с persistent view, а его `message_id` сохраняется в базе.
7. Staff работает через кнопки, а `TicketService` меняет статус и перерисовывает главное сообщение тикета.
8. При закрытии собираются transcript, запись в лог, DM пользователю, после чего канал удаляется.

Ключевые точки:

- `TicketControlView` должен оставаться persistent.
- `message_id` в `TicketRepository` нужен для редактирования главного сообщения тикета.
- проверка staff-доступа централизована в `TicketService`.
- `renderers.py` и `notifications.py` отделены от orchestration-слоя.

## Хранение данных

- `data/tickets.sqlite3` - тикеты и `guild_settings` модуля `tickets`.
- `data/kompromat.sqlite3` - архив компромата и guild-настройки модуля `kompromat`.
- `data/panel_registry.sqlite3` - опубликованные panel messages и их записи для `tickets`, `welcome`, `rules`, `roles`, `kompromat`.

SQLite используется там, где есть состояние, история, поиск или связь с опубликованными сообщениями.

Репозитории закрывают соединения после операций. Для Windows это важно из-за file locking.

## Тесты

Тесты запускаются через `unittest`, а `tests/support.py` добавляет `src` в `sys.path`, поэтому их можно запускать прямо из корня репозитория.

Полный прогон:

```bash
py -3 -m unittest discover -s tests -v
py -3 -m compileall src tests
```

Что покрыто автотестами:

- `tests/test_time_of_day.py` - границы периодов суток и fallback при выборе баннера.
- `tests/test_ticket_channel_ops.py` - извлечение темы тикета и нормализация имени канала.
- `tests/test_tickets_repository.py` - lifecycle тикета и CRUD для `guild_settings`.
- `tests/test_roles_repository.py` - CRUD состояния role-панели в SQLite.
- `tests/test_panel_registry.py` - реестр панелей в SQLite.
- `tests/test_kompromat_repository.py` - создание записи, привязка архивного канала, поиск по tagged user и отметка доказательств.
- `tests/test_presence_module.py` - склонение строки для presence.
