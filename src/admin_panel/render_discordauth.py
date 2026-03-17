from __future__ import annotations

import html
from urllib.parse import urlencode

from .render_models import (
    DashboardPageData,
    DiscordAuthChartPointView,
    DiscordAuthEventView,
    DiscordAuthPlayerView,
)

def build_dashboard_href(
    *,
    tab: str,
    player_uuid: str | None = None,
    search: str = "",
    filter_value: str = "all",
) -> str:
    params: list[tuple[str, str]] = [("tab", "panel" if tab in {"panel", "bot"} else "server")]
    if player_uuid:
        params.append(("player_uuid", player_uuid))
    if search:
        params.append(("discordauth_search", search))
    if filter_value and filter_value != "all":
        params.append(("discordauth_filter", filter_value))
    query = urlencode(params)
    return f"/?{query}" if query else "/"


def render_discordauth_badges(player: DiscordAuthPlayerView) -> str:
    badges = [
        f'<span class="player-tag {html.escape(player.access_badge_class)}">{html.escape(player.access_label)}</span>',
        (
            '<span class="player-tag">Привязан</span>'
            if player.linked
            else '<span class="player-tag player-tag-muted">Не привязан</span>'
        ),
    ]
    if player.pending_session_active:
        badges.append('<span class="player-tag player-tag-warn">Ждёт подтверждения</span>')
    if player.temp_ban_active:
        badges.append('<span class="player-tag player-tag-blocked">Временный бан</span>')
    if player.is_online:
        badges.append('<span class="player-tag player-tag-online">Онлайн</span>')
    return "".join(badges)


def _build_line_chart(points: tuple[DiscordAuthChartPointView, ...]) -> str:
    if not points:
        return '<div class="chart-empty">История ещё не накопилась.</div>'

    width = 640
    height = 220
    padding_x = 20
    padding_y = 18
    plot_width = width - (padding_x * 2)
    plot_height = height - (padding_y * 2)
    max_value = max(point.primary_value for point in points) or 1
    denominator = max(len(points) - 1, 1)

    coordinates: list[tuple[float, float]] = []
    for index, point in enumerate(points):
        x = padding_x + (plot_width * index / denominator)
        y = padding_y + plot_height - ((point.primary_value / max_value) * plot_height)
        coordinates.append((x, y))

    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in coordinates)
    area = " ".join(
        [f"{coordinates[0][0]:.2f},{height - padding_y:.2f}", polyline, f"{coordinates[-1][0]:.2f},{height - padding_y:.2f}"]
    )
    grid = "".join(
        f'<line x1="{padding_x}" y1="{padding_y + plot_height * step / 4:.2f}" x2="{width - padding_x}" y2="{padding_y + plot_height * step / 4:.2f}" />'
        for step in range(5)
    )
    label_indexes = sorted({0, len(points) // 2, len(points) - 1})
    labels = "".join(
        f'<text x="{coordinates[index][0]:.2f}" y="{height - 4}" text-anchor="middle">{html.escape(points[index].label)}</text>'
        for index in label_indexes
    )
    value_labels = "".join(
        f'<text x="{padding_x - 6}" y="{padding_y + plot_height * step / 4 + 4:.2f}" text-anchor="end">{int(round(max_value - (max_value * step / 4)))}</text>'
        for step in range(5)
    )
    point_markers = "".join(
        (
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.5" fill="#f8dfb8" stroke="#8ea8f6" stroke-width="2">'
            f"<title>{html.escape(point.title or f'{point.label}: {point.primary_value}')}</title>"
            "</circle>"
        )
        for point, (x, y) in zip(points, coordinates)
    )
    current_value = points[-1].primary_value
    return f"""
      <div class="chart-shell">
        <svg viewBox="0 0 {width} {height}" class="chart-svg line-chart" role="img" aria-label="История онлайна">
          <g class="chart-guide">{grid}</g>
          <path class="chart-area" d="M {area} Z"></path>
          <polyline class="chart-line" points="{polyline}"></polyline>
          <g class="chart-axis">{value_labels}{labels}</g>
          <g class="chart-points">{point_markers}</g>
        </svg>
        <div class="chart-foot">
          <span>Сейчас: <strong>{current_value}</strong></span>
          <span>Пик: <strong>{max_value}</strong></span>
        </div>
      </div>
    """


def _build_activity_chart(points: tuple[DiscordAuthChartPointView, ...]) -> str:
    if not points:
        return '<div class="chart-empty">История активности ещё не накопилась.</div>'

    width = 640
    height = 220
    padding_x = 24
    padding_y = 22
    plot_width = width - (padding_x * 2)
    plot_height = height - (padding_y * 2)
    group_width = plot_width / max(len(points), 1)
    bar_width = max(group_width * 0.26, 10.0)
    max_value = max(max(point.primary_value, point.secondary_value) for point in points) or 1

    bars: list[str] = []
    labels: list[str] = []
    for index, point in enumerate(points):
        group_x = padding_x + (group_width * index)
        login_height = (point.primary_value / max_value) * plot_height
        link_height = (point.secondary_value / max_value) * plot_height
        login_x = group_x + (group_width * 0.18)
        link_x = group_x + (group_width * 0.56)
        login_y = padding_y + plot_height - login_height
        link_y = padding_y + plot_height - link_height
        title = html.escape(point.title or point.label)
        bars.append(
            f'<rect class="chart-bar chart-bar-login" x="{login_x:.2f}" y="{login_y:.2f}" width="{bar_width:.2f}" height="{login_height:.2f}"><title>{title}: логины {point.primary_value}</title></rect>'
        )
        bars.append(
            f'<rect class="chart-bar chart-bar-link" x="{link_x:.2f}" y="{link_y:.2f}" width="{bar_width:.2f}" height="{link_height:.2f}"><title>{title}: привязки {point.secondary_value}</title></rect>'
        )
        labels.append(
            f'<text x="{group_x + group_width / 2:.2f}" y="{height - 4}" text-anchor="middle">{html.escape(point.label)}</text>'
        )

    grid = "".join(
        f'<line x1="{padding_x}" y1="{padding_y + plot_height * step / 4:.2f}" x2="{width - padding_x}" y2="{padding_y + plot_height * step / 4:.2f}" />'
        for step in range(5)
    )
    total_logins = sum(point.primary_value for point in points)
    total_links = sum(point.secondary_value for point in points)
    return f"""
      <div class="chart-shell">
        <svg viewBox="0 0 {width} {height}" class="chart-svg bar-chart" role="img" aria-label="Активность входов и привязок">
          <g class="chart-guide">{grid}</g>
          {''.join(bars)}
          <g class="chart-axis">{''.join(labels)}</g>
        </svg>
        <div class="chart-foot">
          <span>Логины: <strong>{total_logins}</strong></span>
          <span>Привязки: <strong>{total_links}</strong></span>
        </div>
      </div>
    """


def _build_sanction_chart(points: tuple[DiscordAuthChartPointView, ...]) -> str:
    if not points:
        return '<div class="chart-empty">История санкций еще не накопилась.</div>'

    width = 640
    height = 220
    padding_x = 24
    padding_y = 22
    plot_width = width - (padding_x * 2)
    plot_height = height - (padding_y * 2)
    group_width = plot_width / max(len(points), 1)
    bar_width = max(group_width * 0.46, 12.0)
    max_value = max(point.primary_value for point in points) or 1

    bars: list[str] = []
    labels: list[str] = []
    for index, point in enumerate(points):
        group_x = padding_x + (group_width * index)
        bar_height = (point.primary_value / max_value) * plot_height
        bar_x = group_x + (group_width - bar_width) / 2
        bar_y = padding_y + plot_height - bar_height
        title = html.escape(point.title or point.label)
        bars.append(
            f'<rect class="chart-bar chart-bar-ban" x="{bar_x:.2f}" y="{bar_y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}"><title>{title}: санкции {point.primary_value}</title></rect>'
        )
        labels.append(
            f'<text x="{group_x + group_width / 2:.2f}" y="{height - 4}" text-anchor="middle">{html.escape(point.label)}</text>'
        )

    grid = "".join(
        f'<line x1="{padding_x}" y1="{padding_y + plot_height * step / 4:.2f}" x2="{width - padding_x}" y2="{padding_y + plot_height * step / 4:.2f}" />'
        for step in range(5)
    )
    total_sanctions = sum(point.primary_value for point in points)
    return f"""
      <div class="chart-shell">
        <svg viewBox="0 0 {width} {height}" class="chart-svg bar-chart" role="img" aria-label="История санкций">
          <g class="chart-guide">{grid}</g>
          {''.join(bars)}
          <g class="chart-axis">{''.join(labels)}</g>
        </svg>
        <div class="chart-foot">
          <span>Санкции: <strong>{total_sanctions}</strong></span>
          <span>Пик за день: <strong>{max_value}</strong></span>
        </div>
      </div>
    """


def _render_event_list(events: tuple[DiscordAuthEventView, ...], *, empty_message: str) -> str:
    if not events:
        return f'<div class="player-empty">{html.escape(empty_message)}</div>'

    items = []
    for event in events:
        reason_line = ""
        if event.reason:
            reason_line = f'<p>{html.escape(event.reason)}</p>'
        items.append(
            f'''
            <div class="player-detail-card">
              <div class="player-row-head">
                <strong>{html.escape(event.title)}</strong>
                <span class="player-tag {html.escape(event.badge_class)}">{html.escape(event.event_type)}</span>
              </div>
              <div class="player-row-meta">
                <span>{html.escape(event.subtitle)}</span>
              </div>
              {reason_line}
            </div>
            '''
        )
    return "".join(items)


def render_discordauth_panel(data: DashboardPageData) -> str:
    summary = data.discordauth_summary
    metrics = data.discordauth_metrics
    player_rows = ""
    for player in data.discordauth_players:
        row_class = "player-row is-selected" if data.discordauth_selected_player is not None and data.discordauth_selected_player.player_uuid == player.player_uuid else "player-row"
        href = build_dashboard_href(
            tab="panel",
            player_uuid=player.player_uuid,
            search=data.discordauth_search,
            filter_value=data.discordauth_filter,
        )
        discord_line = (
            f"<span>Discord: {html.escape(player.discord_label)}</span>"
            if player.linked
            else "<span>Discord: не привязан</span>"
        )
        pending_line = ""
        if player.pending_session_active:
            pending_line = f"<span>{html.escape(player.pending_session_label)}</span>"
        ban_line = ""
        if player.temp_ban_active:
            ban_line = f"<span>Бан до {html.escape(player.temp_ban_until_label)}</span>"
        player_rows += f"""
          <a class="{row_class}" href="{html.escape(href)}">
            <div class="player-row-main">
              <div class="player-row-head">
                <strong>{html.escape(player.player_name)}</strong>
                {render_discordauth_badges(player)}
              </div>
              <div class="player-row-meta">
                <span>UUID: {html.escape(player.player_uuid)}</span>
                {discord_line}
                {pending_line}
                {ban_line}
              </div>
            </div>
            <div class="player-row-side">
              <span>{'Онлайн с' if player.is_online else 'Последний вход'}</span>
              <span>{html.escape(player.online_since_label if player.is_online else player.last_authenticated_label)}</span>
              <span>{html.escape(player.last_ip or "IP не сохранён")}</span>
            </div>
          </a>
"""

    if not player_rows:
        player_rows = """
          <div class="player-empty">
            <strong>Игроки не найдены</strong>
            Измени поиск или фильтр. Когда мод запишет новых игроков, они появятся здесь автоматически.
          </div>
"""

    filter_options = {
        "all": "Все игроки",
        "linked": "Привязанные",
        "online": "Онлайн",
        "blocked": "Запрещённые",
        "banned": "С баном",
        "pending": "Ждут вход",
    }
    filter_html = "".join(
        (
            f'<option value="{html.escape(value)}"{" selected" if data.discordauth_filter == value else ""}>'
            f"{html.escape(label)}</option>"
        )
        for value, label in filter_options.items()
    )

    summary_cards = ""
    if summary is not None:
        summary_cards = f"""
    <section class="summary-grid" style="margin-top: 16px;">
      <article class="summary-card">
        <strong>Игроки</strong>
        <b>{summary.total_players}</b>
        <span>известных записей DiscordAuth</span>
      </article>
      <article class="summary-card">
        <strong>Привязки</strong>
        <b>{summary.linked_players}</b>
        <span>игроков уже связаны с Discord</span>
      </article>
      <article class="summary-card">
        <strong>Онлайн</strong>
        <b>{summary.online_players}</b>
        <span>авторизованных игроков прямо сейчас</span>
      </article>
      <article class="summary-card">
        <strong>Пермабаны</strong>
        <b>{summary.blocked_players}</b>
        <span>игроков сейчас вручную заблокированы</span>
      </article>
      <article class="summary-card">
        <strong>Темпбаны</strong>
        <b>{summary.temp_banned_players}</b>
        <span>активных временных ограничений</span>
      </article>
    </section>
"""

    charts_section = ""
    if metrics is not None:
        charts_section = f"""
    <section class="chart-grid" style="margin-top: 16px;">
      <article class="card chart-card">
        <div class="chart-card-head">
          <div>
            <h2>Онлайн за 24 часа</h2>
            <p>График строится по снапшотам присутствия с игрового сервера.</p>
          </div>
        </div>
        {_build_line_chart(metrics.online_history)}
      </article>
      <article class="card chart-card">
        <div class="chart-card-head">
          <div>
            <h2>Входы и привязки за 7 дней</h2>
            <p>Синие столбцы показывают входы, золотые — новые привязки.</p>
          </div>
        </div>
        {_build_activity_chart(metrics.activity_history)}
      </article>
    </section>
"""

    selected = data.discordauth_selected_player
    detail_section = """
        <div class="player-empty">
          <strong>Выбери игрока слева</strong>
          Здесь появятся данные об аккаунте, текущем режиме допуска, временном бане и быстрых действиях.
        </div>
"""
    if selected is not None:
        context_fields = (
            f'<input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">'
            '<input type="hidden" name="tab" value="panel">'
            f'<input type="hidden" name="player_uuid" value="{html.escape(selected.player_uuid)}">'
            f'<input type="hidden" name="discordauth_search" value="{html.escape(data.discordauth_search)}">'
            f'<input type="hidden" name="discordauth_filter" value="{html.escape(data.discordauth_filter)}">'
        )
        selected_discord = (
            f'<a href="{html.escape(selected.discord_profile_url or "#")}">{html.escape(selected.discord_label)}</a>'
            if selected.linked and selected.discord_profile_url
            else "Не привязан"
        )
        pending_block = ""
        if selected.pending_session_active and selected.pending_session_id is not None:
            pending_block = f"""
            <section class="player-action-group">
              <h3>Активный запрос на вход</h3>
              <div class="player-detail-card">
                <div class="player-info-list">
                  <div class="player-info-line">
                    <strong>Состояние</strong>
                    <span>{html.escape(selected.pending_session_label)}</span>
                  </div>
                  <div class="player-info-line">
                    <strong>IP</strong>
                    <span>{html.escape(selected.pending_session_address or "Не передан")}</span>
                  </div>
                </div>
                <form method="post" action="/action" class="player-inline-form">
                  {context_fields}
                  <input type="hidden" name="action" value="discordauth_cancel_session">
                  <input type="hidden" name="session_id" value="{html.escape(selected.pending_session_id)}">
                  <button type="submit" class="secondary">Сбросить запрос</button>
                </form>
              </div>
            </section>
"""
    if selected is not None:
        selected_history_markup = _render_event_list(
            data.discordauth_selected_restrictions,
            empty_message="Для этого игрока санкции пока не выдавались.",
        )
        detail_section = f"""
        <div class="player-detail-grid">
          <section class="player-detail-card">
            <div class="player-detail-head">
              <div>
                <h3>{html.escape(selected.player_name)}</h3>
                <p>{render_discordauth_badges(selected)}</p>
              </div>
            </div>
            <div class="player-info-list">
              <div class="player-info-line">
                <strong>UUID</strong>
                <span>{html.escape(selected.player_uuid)}</span>
              </div>
              <div class="player-info-line">
                <strong>Discord</strong>
                <span>{selected_discord}</span>
              </div>
              <div class="player-info-line">
                <strong>Последний IP</strong>
                <span>{html.escape(selected.last_ip or "IP не сохранен")}</span>
              </div>
              <div class="player-info-line">
                <strong>Последний вход</strong>
                <span>{html.escape(selected.last_authenticated_label)}</span>
              </div>
              <div class="player-info-line">
                <strong>Статус</strong>
                <span>{'Онлайн' if selected.is_online else 'Оффлайн'}</span>
              </div>
              <div class="player-info-line">
                <strong>Онлайн с</strong>
                <span>{html.escape(selected.online_since_label if selected.is_online else 'Сейчас не в игре')}</span>
              </div>
              <div class="player-info-line">
                <strong>Последний пинг</strong>
                <span>{html.escape(selected.last_seen_label)}</span>
              </div>
              <div class="player-info-line">
                <strong>Темпбан</strong>
                <span>{html.escape(selected.temp_ban_until_label if selected.temp_ban_active else "Нет")}</span>
              </div>
              <div class="player-info-line">
                <strong>Причина темпбана</strong>
                <span>{html.escape(selected.temp_ban_reason or "Не указана")}</span>
              </div>
              <div class="player-info-line">
                <strong>Причина пермабана</strong>
                <span>{html.escape(selected.block_reason or "Не указана")}</span>
              </div>
            </div>
          </section>

          <section class="player-actions">
            <section class="player-action-group">
              <h3>Доступ к серверу</h3>
              <div class="player-action-grid">
                <form method="post" action="/action" class="player-inline-form">
                  {context_fields}
                  <input type="hidden" name="action" value="discordauth_set_access">
                  <input type="hidden" name="access_state" value="ALLOWED">
                  <button type="submit">Разрешить</button>
                </form>
                <form method="post" action="/action" class="player-inline-form">
                  {context_fields}
                  <input type="hidden" name="action" value="discordauth_set_access">
                  <input type="hidden" name="access_state" value="AUTO">
                  <button type="submit" class="secondary">Сбросить в авто</button>
                </form>
              </div>
            </section>

            <section class="player-action-group">
              <h3>Перманентный бан</h3>
              <form method="post" action="/action" class="player-stack-form">
                {context_fields}
                <input type="hidden" name="action" value="discordauth_ban_player">
                <label for="perm_ban_reason">Причина</label>
                <textarea id="perm_ban_reason" name="reason" rows="4" placeholder="Почему игроку закрыт доступ"></textarea>
                <button type="submit" class="danger">Выдать пермабан</button>
              </form>
            </section>

            <section class="player-action-group">
              <h3>Временный бан</h3>
              <form method="post" action="/action" class="player-stack-form">
                {context_fields}
                <input type="hidden" name="action" value="discordauth_set_temp_ban">
                <label for="ban_minutes">Минуты</label>
                <input id="ban_minutes" name="minutes" type="number" min="1" placeholder="60" required>
                <label for="ban_reason">Причина</label>
                <textarea id="ban_reason" name="reason" rows="4" placeholder="Кратко опиши причину"></textarea>
                <button type="submit">Выдать темпбан</button>
              </form>
              <form method="post" action="/action" class="player-inline-form">
                {context_fields}
                <input type="hidden" name="action" value="discordauth_clear_temp_ban">
                <button type="submit" class="secondary">Снять темпбан</button>
              </form>
            </section>

            {pending_block}

            <section class="player-action-group">
              <h3>История ограничений</h3>
              {selected_history_markup}
            </section>

            <section class="player-action-group">
              <h3>Привязка</h3>
              <form method="post" action="/action" class="player-inline-form">
                {context_fields}
                <input type="hidden" name="action" value="discordauth_unlink_player">
                <button type="submit" class="danger">Сбросить привязку</button>
              </form>
            </section>
          </section>
        </div>
"""

    history_section = ""
    if data.discordauth_recent_restrictions:
        history_section = f"""
    <section class="grid" style="margin-top: 16px;">
      <article class="card">
        <h2>Последние санкции</h2>
        {_render_event_list(data.discordauth_recent_restrictions, empty_message="История санкций пока пуста.")}
      </article>
    </section>
"""

    reset_href = build_dashboard_href(tab="panel")
    return f"""
    {summary_cards}
    {charts_section}

    <section class="grid" style="margin-top: 16px;">
      <article class="card">
        <h2>Игроки DiscordAuth</h2>
        <form method="get" action="/" class="player-toolbar" data-discordauth-filter-form>
          <input type="hidden" name="tab" value="panel">
          <div class="player-search-row">
            <div>
              <label for="discordauth_search">Поиск</label>
              <input
                id="discordauth_search"
                name="discordauth_search"
                type="search"
                placeholder="Ник, UUID или Discord ID"
                value="{html.escape(data.discordauth_search)}"
              >
            </div>
            <div>
              <label for="discordauth_filter">Фильтр</label>
              <select id="discordauth_filter" name="discordauth_filter" data-discordauth-filter-input>
                {filter_html}
              </select>
            </div>
            <div class="player-action-grid">
              <button type="submit" class="secondary">Показать</button>
              <a href="{html.escape(reset_href)}" class="button-link">Сбросить</a>
            </div>
          </div>
        </form>
        <div class="player-list">
          {player_rows}
        </div>
      </article>

      <article class="card">
        <h2>Карточка игрока</h2>
        {detail_section}
      </article>
    </section>
    {history_section}
"""
