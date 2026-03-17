from __future__ import annotations

import html

from .render_assets import DASHBOARD_SCRIPT, DASHBOARD_STYLES, LOGIN_STYLES
from .render_discordauth import render_discordauth_panel
from .render_helpers import build_branch_picker, render_avatar
from .render_models import DashboardPageData, HERO_DESCRIPTION, LoginPageData

def render_login_page(data: LoginPageData) -> str:
    brand_title = "Warlords Bot"
    error_block = ""
    if data.error:
        error_block = f'<div class="flash flash-error">{html.escape(data.error)}</div>'

    discord_block = ""
    if data.discord_login_url:
        discord_block = (
            '<div class="login-actions">'
            f'<a class="discord-button" href="{html.escape(data.discord_login_url)}">Войти через Discord</a>'
            "</div>"
        )

    password_block = ""
    if data.password_enabled:
        divider = '<div class="divider">или</div>' if discord_block else ""
        password_block = (
            f"{divider}"
            '<form method="post" action="/login">'
            '<label for="password">Пароль панели</label>'
            '<input id="password" name="password" type="password" autocomplete="current-password" required>'
            '<button type="submit">Войти</button>'
            "</form>"
        )

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{brand_title}</title>
{LOGIN_STYLES}
</head>
<body>
  <main class="panel">
    <h1>{brand_title}</h1>
    <p>Панель управления Discord-ботом. Войди через Discord, чтобы открыть дашборд и управлять доступом других админов.</p>
    {error_block}
    {discord_block}
    {password_block}
  </main>
</body>
</html>"""

def render_dashboard_page(data: DashboardPageData) -> str:
    active_state = data.service_data.get("ActiveState", "unknown")
    status_class = "status-running" if active_state == "active" else "status-stopped"
    start_disabled = "disabled" if active_state == "active" else ""
    stop_disabled = "disabled" if active_state != "active" else ""
    branch_picker = build_branch_picker(data.git_data.current_branch, data.git_data.branches)
    switch_disabled = "disabled" if not data.git_data.branches else ""

    flash_block = ""
    if data.flash is not None:
        flash_block = (
            f'<section class="card flash flash-{html.escape(data.flash.level)}">'
            f"<h2>{html.escape(data.flash.title)}</h2>"
            f"<pre>{html.escape(data.flash.output or 'Готово.')}</pre>"
            "</section>"
        )

    user_chip = ""
    if data.current_user is not None:
        user_chip = (
            '<div class="user-chip">'
            f"{render_avatar(data.current_user.display_name, data.current_user.avatar_url)}"
            '<div class="user-meta">'
            f"<strong>{html.escape(data.current_user.display_name)}</strong>"
            f"<span>{html.escape(data.current_user.user_id)}</span>"
            "</div>"
            "</div>"
        )

    access_section = ""
    if data.discord_auth_enabled:
        items: list[str] = []
        for allowed_user in data.allowed_users:
            remove_control = (
                '<span class="badge">Защищён</span>'
                if not allowed_user.removable
                else (
                    '<form method="post" action="/action">'
                    f'<input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">'
                    '<input type="hidden" name="action" value="remove_allowed_user">'
                    f'<input type="hidden" name="target_user_id" value="{html.escape(allowed_user.user_id)}">'
                    '<button type="submit" class="secondary inline-button">Убрать</button>'
                    "</form>"
                )
            )
            display_name = allowed_user.display_name or allowed_user.username or "Discord-пользователь"
            secondary = allowed_user.username if allowed_user.username and allowed_user.username != display_name else allowed_user.user_id
            items.append(
                '<div class="access-item">'
                '<div class="access-item-user">'
                f"{render_avatar(display_name, allowed_user.avatar_url)}"
                '<div class="access-item-meta">'
                f"<strong>{html.escape(display_name)}</strong>"
                f"<span>{html.escape(secondary)}</span>"
                "</div>"
                "</div>"
                f"{remove_control}"
                "</div>"
            )
        access_section = f"""

    <section class="card" style="margin-top: 16px;">
      <h2>Доступ к панели</h2>
      <div class="access-grid">
        <form method="post" action="/action" class="access-form">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="allow_user">
          <div>
            <label for="discord_user_id">Discord ID</label>
            <input id="discord_user_id" name="discord_user_id" type="text" inputmode="numeric" pattern="[0-9]+" placeholder="1034533546863382649" required>
          </div>
          <button type="submit">Выдать доступ</button>
          <p class="hint">Добавь Discord ID тех пользователей, которым можно открывать эту панель.</p>
        </form>
        <div class="access-list">
          {''.join(items) or '<p class="hint">Пока нет пользователей с доступом.</p>'}
        </div>
      </div>
    </section>"""

    module_cards = "".join(
        f'''
      <article class="module-card">
        <strong>{html.escape(module.name)}</strong>
        <p>{html.escape(module.description)}</p>
        <code>{html.escape(module.state)}</code>
        <p style="margin-top: 12px;">{html.escape(module.meta)}</p>
      </article>
''' for module in data.bot_modules
    ) or """
      <article class="module-card">
        <strong>Модули</strong>
        <p>Пока не удалось получить список модулей бота.</p>
        <code>нет данных</code>
      </article>
"""
    discordauth_panel = render_discordauth_panel(data)
    active_tab = "panel" if data.active_tab == "panel" else "server"
    server_tab_button_class = "view-tab is-active" if active_tab == "server" else "view-tab"
    panel_tab_button_class = "view-tab is-active" if active_tab == "panel" else "view-tab"
    server_tab_panel_class = "dashboard-tab is-active" if active_tab == "server" else "dashboard-tab"
    panel_tab_panel_class = "dashboard-tab is-active" if active_tab == "panel" else "dashboard-tab"

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Warlords Bot</title>
{DASHBOARD_STYLES}
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Warlords Control</p>
        <h1>Warlords Panel</h1>
        <p>{html.escape(HERO_DESCRIPTION)}</p>
        <div class="view-tabs" role="tablist" aria-label="Разделы панели">
          <button type="button" class="{server_tab_button_class}" data-dashboard-tab="server">Сервер</button>
          <button type="button" class="{panel_tab_button_class}" data-dashboard-tab="panel">Панель</button>
        </div>
      </div>
      <div class="hero-actions">
        {user_chip}
        <a href="/">Обновить</a>
        <form method="post" action="/logout">
          <button type="submit">Выйти</button>
        </form>
      </div>
    </section>

    {flash_block}

    <section class="{server_tab_panel_class}" data-tab-panel="server">
    <section class="grid">
      <article class="card">
        <h2>Сервис</h2>
        <div class="status-pill {status_class}">{html.escape(data.service_data.get("status_text", "Неизвестно"))}</div>
        <dl>
          <dt>Systemd unit</dt>
          <dd>{html.escape(data.service_data.get("Id", data.service_name))}</dd>
          <dt>Основной PID</dt>
          <dd>{html.escape(data.service_data.get("MainPID", "0"))}</dd>
          <dt>Активен с</dt>
          <dd>{html.escape(data.service_data.get("ActiveEnterTimestamp", "n/a"))}</dd>
          <dt>Файл unit</dt>
          <dd>{html.escape(data.service_data.get("FragmentPath", "n/a"))}</dd>
        </dl>
      </article>

      <article class="card">
        <h2>Git</h2>
        <dl>
          <dt>Remote</dt>
          <dd>{html.escape(data.git_data.remote_name)}</dd>
          <dt>Remote URL</dt>
          <dd>{html.escape(data.git_data.remote_url)}</dd>
          <dt>Текущая ветка</dt>
          <dd>{html.escape(data.git_data.current_branch)}</dd>
          <dt>Upstream</dt>
          <dd>{html.escape(data.git_data.upstream or "не задан")}</dd>
          <dt>Tracking</dt>
          <dd>{html.escape(data.tracking_status)}</dd>
          <dt>Worktree</dt>
          <dd>{html.escape(data.git_data.worktree_status)}</dd>
          <dt>Коммит</dt>
          <dd>{html.escape(data.git_data.commit)}</dd>
          <dt>Последнее сообщение</dt>
          <dd>{html.escape(data.git_data.subject)}</dd>
        </dl>
      </article>
    </section>

    <section class="card section-actions" style="margin-top: 16px;">
      <h2>Действия сервиса</h2>
      <div class="actions">
        <form method="post" action="/action">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="start">
          <button type="submit" {start_disabled}>Запустить</button>
        </form>
        <form method="post" action="/action">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="restart">
          <button type="submit" class="secondary">Перезапустить</button>
        </form>
        <form method="post" action="/action">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="stop">
          <button type="submit" class="danger" {stop_disabled}>Остановить</button>
        </form>
        <form method="post" action="/action">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="update">
          <button type="submit">Обновить текущую ветку</button>
        </form>
      </div>
      <p class="hint">Обновление использует текущую git-ветку, делает fetch и pull --ff-only, обновляет зависимости и перезапускает сервис бота.</p>
    </section>

    <section class="card section-branches" style="margin-top: 16px;">
      <h2>Ветки</h2>
      <div class="actions" style="margin-bottom: 12px;">
        <form method="post" action="/action">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="fetch">
          <button type="submit" class="secondary">Обновить refs</button>
        </form>
      </div>
      <form method="post" action="/action" class="switcher">
        <div>
{branch_picker}
        </div>
        <div class="switcher-submit">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="switch_branch">
          <button type="submit" class="secondary" {switch_disabled}>Переключить ветку</button>
        </div>
      </form>
      <p class="hint">После переключения панель подтянет выбранную ветку, обновит зависимости и перезапустит сервис бота.</p>
    </section>

    {access_section}

    <section class="card log-card">
      <h2>Последние логи</h2>
      <pre>{html.escape(data.logs)}</pre>
    </section>
    <section class="card" style="margin-top: 16px;">
      <h2>Модули бота</h2>
      <div class="module-grid">
{module_cards}
      </div>
    </section>
    </section>

    <section class="{panel_tab_panel_class}" data-tab-panel="panel">
    <div data-discordauth-root id="discordauth-panel-root">
    {discordauth_panel}
    </div>
    </section>
  </main>
{DASHBOARD_SCRIPT}
</body>
</html>"""
