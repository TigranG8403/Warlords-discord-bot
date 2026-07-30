# Production deployment

Эта схема отделяет код, конфигурацию и изменяемые данные:

```text
/opt/warlords-bot-runtime/
├── current -> releases/<commit-sha>
└── releases/

/var/lib/warlords-bot/data/
/etc/warlords-bot.env
```

## Первая установка

Команды выполняются от `root`.

```bash
groupadd --system warlords-bot
useradd --system --gid warlords-bot --home /var/lib/warlords-bot --shell /usr/sbin/nologin warlords-bot
install -d -o root -g root -m 0755 /opt/warlords-bot-runtime
install -d -o warlords-bot -g warlords-bot -m 0750 /var/lib/warlords-bot/data

install -o root -g root -m 0755 deploy/deploy.sh /usr/local/sbin/warlords-bot-deploy
install -o root -g root -m 0644 deploy/warlords-bot.service /etc/systemd/system/warlords-bot.service
install -o root -g root -m 0644 deploy/warlords-bot-deploy.service /etc/systemd/system/warlords-bot-deploy.service
install -o root -g root -m 0644 deploy/warlords-bot-deploy.path /etc/systemd/system/warlords-bot-deploy.path
```

Создать root-only файл `/etc/warlords-bot.env`:

```env
DISCORD_TOKEN=
APP_COMMAND_GUILD_ID=
ENABLED_MODULES=tickets,welcome,rules,roles,kompromat,presence,flytrap,maintenance
BOT_UPDATE_ALLOWED_USER_IDS=
```

```bash
chown root:root /etc/warlords-bot.env
chmod 0600 /etc/warlords-bot.env
systemctl daemon-reload
systemctl start warlords-bot-deploy.service
systemctl enable warlords-bot.service
systemctl enable --now warlords-bot-deploy.path
```

Для одноразового перехода со старой установки `/opt/warlords-bot` вместо этих
шагов используется migration runner. Он сохраняет units, конфигурацию и
консистентные копии всех SQLite-баз, а при ошибке возвращает прежний сервис:

```bash
sudo deploy/migrate_legacy.sh v2
```

## Обновление

Из Discord:

```text
/bot update
```

Либо с сервера:

```bash
systemctl start warlords-bot-deploy.service
journalctl -u warlords-bot-deploy.service -n 200 --no-pager
```

Ветка по умолчанию — `v2`. Переопределения хранятся в необязательном root-only
файле `/etc/warlords-bot-deploy.env`:

```env
WARLORDS_BOT_RELEASE_BRANCH=v2
WARLORDS_BOT_REPOSITORY_URL=https://github.com/TigranG8403/Warlords-multipurpose-bot.git
```

Бот не имеет прав на Git, release-каталоги, `systemctl` или `sudo`. Он может
только создать `/var/lib/warlords-bot/deploy.request`; запуском root-owned
deployment unit занимается `warlords-bot-deploy.path`.
