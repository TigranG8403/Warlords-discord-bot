from __future__ import annotations

import html
from dataclasses import dataclass

from .git_ops import GitSnapshot


@dataclass(frozen=True)
class FlashMessage:
    level: str
    title: str
    output: str


@dataclass(frozen=True)
class LoginPageData:
    title: str
    error: str | None = None


@dataclass(frozen=True)
class DashboardPageData:
    csrf_token: str
    service_name: str
    service_data: dict[str, str]
    git_data: GitSnapshot
    tracking_status: str
    logs: str
    flash: FlashMessage | None


DASHBOARD_REFRESH_SECONDS = 240
HERO_DESCRIPTION = "Панель для управления ботом, сервисом и ветками."


LOGIN_STYLES = """
  <style>
    :root {
      color-scheme: dark;
      --bg: #120f0d;
      --panel: rgba(27, 22, 19, 0.92);
      --line: rgba(208, 161, 95, 0.28);
      --line-strong: rgba(208, 161, 95, 0.45);
      --text: #f1e7d3;
      --muted: #c7b89d;
      --accent: #d0a15f;
      --accent-strong: #efc98f;
      --danger: #c85b4c;
      --shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
    }
    * { box-sizing: border-box; }
    @keyframes fade-rise {
      from { opacity: 0; transform: translateY(14px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes soft-float {
      0% { transform: translate3d(0, 0, 0) scale(1); }
      50% { transform: translate3d(0, -10px, 0) scale(1.03); }
      100% { transform: translate3d(0, 0, 0) scale(1); }
    }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--text);
      background:
        radial-gradient(circle at top, rgba(208, 161, 95, 0.17), transparent 35%),
        linear-gradient(135deg, #171210, #0d0a09 70%);
      display: grid;
      place-items: center;
      padding: 24px;
      overflow: hidden;
    }
    body::before,
    body::after {
      content: "";
      position: fixed;
      inset: auto;
      border-radius: 999px;
      pointer-events: none;
      filter: blur(18px);
      opacity: 0.45;
      animation: soft-float 12s ease-in-out infinite;
    }
    body::before {
      width: 220px;
      height: 220px;
      top: 7%;
      left: 10%;
      background: rgba(208, 161, 95, 0.15);
    }
    body::after {
      width: 180px;
      height: 180px;
      right: 8%;
      bottom: 10%;
      background: rgba(99, 183, 132, 0.12);
      animation-delay: -5s;
    }
    .panel {
      width: min(100%, 420px);
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(36, 29, 24, 0.95), rgba(22, 17, 14, 0.95));
      border-radius: 18px;
      padding: 28px;
      box-shadow: var(--shadow);
      animation: fade-rise 420ms ease both;
      backdrop-filter: blur(8px);
    }
    h1 {
      margin: 0 0 10px;
      font-size: 28px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    p {
      margin: 0 0 22px;
      color: var(--muted);
      line-height: 1.5;
    }
    label {
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    input {
      width: 100%;
      border: 1px solid var(--line);
      background: rgba(11, 9, 8, 0.9);
      color: var(--text);
      border-radius: 12px;
      padding: 14px 16px;
      font: inherit;
      margin-bottom: 16px;
      transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
    }
    input:focus {
      outline: none;
      border-color: var(--line-strong);
      box-shadow: 0 0 0 4px rgba(208, 161, 95, 0.12);
      transform: translateY(-1px);
    }
    button {
      width: 100%;
      border: 0;
      border-radius: 12px;
      padding: 14px 16px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      color: #1b1208;
      background: linear-gradient(180deg, var(--accent-strong), var(--accent));
      transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease;
    }
    button:hover {
      transform: translateY(-1px);
      box-shadow: 0 12px 30px rgba(208, 161, 95, 0.2);
      filter: brightness(1.03);
    }
    .flash {
      margin-bottom: 16px;
      border-radius: 12px;
      padding: 12px 14px;
      border: 1px solid rgba(200, 91, 76, 0.45);
      background: rgba(200, 91, 76, 0.12);
      color: #ffd6d0;
      animation: fade-rise 280ms ease both;
    }
  </style>
"""


DASHBOARD_STYLES = """
  <style>
    :root {
      color-scheme: dark;
      --bg: #0f0b09;
      --card: rgba(27, 22, 18, 0.94);
      --line: rgba(206, 165, 104, 0.22);
      --line-strong: rgba(206, 165, 104, 0.4);
      --text: #f2e7d3;
      --muted: #b9aa8d;
      --success: #63b784;
      --danger: #cf6c5c;
      --mono: "Consolas", "SFMono-Regular", monospace;
    }
    * { box-sizing: border-box; }
    @keyframes fade-rise {
      from { opacity: 0; transform: translateY(16px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes pulse-dot {
      0% { transform: scale(1); opacity: 1; }
      70% { transform: scale(1.45); opacity: 0.3; }
      100% { transform: scale(1); opacity: 1; }
    }
    @keyframes drift {
      0% { transform: translate3d(0, 0, 0); }
      50% { transform: translate3d(0, -12px, 0); }
      100% { transform: translate3d(0, 0, 0); }
    }
    @keyframes dropdown-bloom {
      0% { opacity: 0.84; transform: translateY(6px) scale(0.98); }
      100% { opacity: 1; transform: translateY(0) scale(1); }
    }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top left, rgba(209, 163, 96, 0.15), transparent 26%),
        radial-gradient(circle at top right, rgba(99, 183, 132, 0.12), transparent 20%),
        linear-gradient(180deg, var(--bg), #090705 72%);
      overflow-x: hidden;
    }
    body::before,
    body::after {
      content: "";
      position: fixed;
      border-radius: 999px;
      pointer-events: none;
      filter: blur(22px);
      opacity: 0.35;
      animation: drift 14s ease-in-out infinite;
    }
    body::before {
      width: 260px;
      height: 260px;
      top: 4rem;
      left: -4rem;
      background: rgba(209, 163, 96, 0.16);
    }
    body::after {
      width: 220px;
      height: 220px;
      right: -3rem;
      top: 12rem;
      background: rgba(99, 183, 132, 0.12);
      animation-delay: -6s;
    }
    .shell {
      width: min(1120px, calc(100% - 32px));
      margin: 28px auto;
    }
    .hero,
    .card {
      animation: fade-rise 420ms ease both;
    }
    .hero {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      align-items: flex-end;
      justify-content: space-between;
      margin-bottom: 18px;
      padding: 22px 24px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: linear-gradient(180deg, rgba(35, 27, 22, 0.95), rgba(17, 13, 10, 0.95));
      backdrop-filter: blur(8px);
    }
    .grid .card:nth-child(1) { animation-delay: 80ms; }
    .grid .card:nth-child(2) { animation-delay: 140ms; }
    .section-actions { animation-delay: 200ms; }
    .section-branches { animation-delay: 260ms; }
    .log-card { margin-top: 16px; animation-delay: 320ms; }
    .eyebrow {
      margin: 0 0 8px;
      color: var(--muted);
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-size: 12px;
    }
    h1 {
      margin: 0;
      font-size: clamp(30px, 4vw, 46px);
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .hero p {
      margin: 12px 0 0;
      max-width: 680px;
      color: var(--muted);
      line-height: 1.6;
    }
    .hero-actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .hero-actions a,
    .hero-actions button {
      border: 1px solid var(--line-strong);
      background: rgba(209, 163, 96, 0.08);
      color: var(--text);
      border-radius: 999px;
      padding: 10px 16px;
      font: inherit;
      text-decoration: none;
      cursor: pointer;
      transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
    }
    .hero-actions a:hover,
    .hero-actions button:hover {
      transform: translateY(-1px);
      border-color: rgba(206, 165, 104, 0.62);
      background: rgba(209, 163, 96, 0.14);
    }
    .hero-actions form { margin: 0; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }
    .card {
      position: relative;
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px;
      background: var(--card);
      backdrop-filter: blur(8px);
      overflow: visible;
      transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }
    .card:hover {
      transform: translateY(-2px);
      border-color: rgba(206, 165, 104, 0.36);
      box-shadow: 0 18px 45px rgba(0, 0, 0, 0.18);
    }
    .card h2 {
      margin: 0 0 16px;
      font-size: 14px;
      color: var(--muted);
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 14px;
      border: 1px solid var(--line-strong);
      background: rgba(255, 255, 255, 0.03);
      margin-bottom: 16px;
    }
    .status-running::before,
    .status-stopped::before {
      content: "";
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
    }
    .status-running::before {
      background: var(--success);
      animation: pulse-dot 1.8s ease-in-out infinite;
    }
    .status-stopped::before { background: var(--danger); }
    dl {
      display: grid;
      grid-template-columns: minmax(120px, 160px) 1fr;
      gap: 10px 12px;
      margin: 0;
    }
    dt { color: var(--muted); font-size: 14px; }
    dd {
      margin: 0;
      word-break: break-word;
      font-family: var(--mono);
      font-size: 13px;
    }
    .actions {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }
    .actions form,
    .switcher form { margin: 0; }
    .actions button,
    .switcher-submit button {
      width: 100%;
      border: 0;
      border-radius: 14px;
      padding: 14px 16px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      color: #1a1208;
      background: linear-gradient(180deg, #f0cb92, #d1a360);
      transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease, opacity 180ms ease;
    }
    .actions button:hover,
    .switcher-submit button:hover {
      transform: translateY(-1px);
      box-shadow: 0 14px 28px rgba(208, 161, 95, 0.16);
      filter: brightness(1.03);
    }
    .actions button.danger {
      color: #fff4f2;
      background: linear-gradient(180deg, #db7d70, #b45043);
    }
    .actions button.secondary,
    .switcher-submit button.secondary {
      color: var(--text);
      background: linear-gradient(180deg, #3a3029, #241d18);
      border: 1px solid var(--line-strong);
    }
    .actions button:disabled,
    .switcher-submit button:disabled {
      cursor: not-allowed;
      opacity: 0.55;
      box-shadow: none;
      transform: none;
    }
    .section-actions,
    .section-branches,
    .log-card {
      position: relative;
    }
    .section-branches {
      z-index: 18;
    }
    .log-card {
      z-index: 4;
    }
    .hint {
      margin: 14px 0 0;
      color: var(--muted);
      line-height: 1.5;
    }
    .switcher {
      display: grid;
      grid-template-columns: minmax(220px, 1fr) minmax(180px, 240px);
      gap: 12px;
      align-items: end;
    }
    .switcher label {
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .branch-picker {
      position: relative;
    }
    .branch-picker__label {
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .branch-picker__trigger {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 14px;
      padding: 14px 16px;
      font: inherit;
      color: #f7f0e3;
      background: #0b0908;
      transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease, background 180ms ease;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
    }
    .branch-picker__trigger:hover {
      transform: translateY(-1px);
      border-color: rgba(206, 165, 104, 0.34);
      background: #14100d;
    }
    .branch-picker__trigger:focus-visible {
      outline: none;
      border-color: rgba(206, 165, 104, 0.34);
      box-shadow: 0 0 0 3px rgba(206, 165, 104, 0.08);
    }
    .branch-picker__trigger[aria-expanded="true"] {
      border-color: rgba(214, 178, 119, 0.38);
      background: #17120f;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02), 0 12px 24px rgba(0, 0, 0, 0.16);
    }
    .branch-picker__value {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      text-align: left;
      color: #f7f0e3;
      font-weight: 700;
      letter-spacing: 0.01em;
      text-shadow: none;
    }
    .branch-picker__caret {
      display: inline-block;
      width: 10px;
      height: 10px;
      border-right: 2px solid #f7f0e3;
      border-bottom: 2px solid #f7f0e3;
      transform: rotate(45deg);
      transition: transform 180ms ease, border-color 180ms ease;
      flex: 0 0 auto;
      position: relative;
      top: 0;
      transform-origin: 50% 40%;
      opacity: 1;
    }
    .branch-picker__menu {
      position: absolute;
      left: 0;
      right: 0;
      top: calc(100% + 10px);
      display: grid;
      gap: 8px;
      padding: 8px;
      border: 1px solid rgba(206, 165, 104, 0.16);
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(29, 22, 18, 0.985), rgba(17, 13, 10, 0.985));
      box-shadow: 0 20px 48px rgba(0, 0, 0, 0.3);
      backdrop-filter: blur(14px);
      opacity: 0;
      transform: translateY(-8px) scale(0.985);
      transform-origin: top center;
      visibility: hidden;
      clip-path: inset(0 0 14px 0 round 16px);
      pointer-events: none;
      transition:
        opacity 180ms ease,
        transform 180ms ease,
        clip-path 180ms ease,
        visibility 0s linear 180ms;
      z-index: 40;
    }
    .branch-picker__option {
      width: 100%;
      border: 1px solid rgba(255, 255, 255, 0.03);
      border-radius: 12px;
      padding: 12px 14px;
      text-align: left;
      font: inherit;
      color: var(--text);
      background: rgba(255, 255, 255, 0.015);
      cursor: pointer;
      opacity: 0.94;
      transform: translateY(-4px);
      transition:
        opacity 180ms ease,
        transform 180ms ease,
        border-color 180ms ease,
        background 180ms ease,
        color 180ms ease,
        box-shadow 180ms ease;
    }
    .branch-picker__option:hover {
      transform: translateY(-1px);
      border-color: rgba(206, 165, 104, 0.22);
      background: rgba(209, 163, 96, 0.1);
    }
    .branch-picker__option.is-selected {
      border-color: rgba(206, 165, 104, 0.24);
      color: #ead9bc;
      background: linear-gradient(180deg, rgba(104, 76, 39, 0.34), rgba(53, 39, 21, 0.52));
      box-shadow: inset 0 1px 0 rgba(255, 244, 224, 0.03);
    }
    .branch-picker__option.is-selected:hover {
      border-color: rgba(219, 179, 114, 0.38);
      color: #f3e7d1;
      background: linear-gradient(180deg, rgba(122, 89, 45, 0.42), rgba(66, 47, 24, 0.58));
      box-shadow: inset 0 1px 0 rgba(255, 244, 224, 0.05);
    }
    .branch-picker__option:disabled,
    .branch-picker__trigger:disabled {
      cursor: not-allowed;
      opacity: 0.6;
      transform: none;
    }
    .branch-picker.is-open .branch-picker__menu {
      opacity: 1;
      transform: translateY(0) scale(1);
      visibility: visible;
      clip-path: inset(0 0 0 0 round 16px);
      pointer-events: auto;
      animation: dropdown-bloom 180ms ease both;
      transition-delay: 0s;
    }
    .branch-picker.is-open .branch-picker__caret {
      transform: rotate(225deg);
      border-color: #fff6e8;
    }
    .branch-picker.is-open .branch-picker__option {
      opacity: 1;
      transform: translateY(0);
    }
    .flash { margin-top: 16px; }
    .flash-success {
      border-color: rgba(99, 183, 132, 0.38);
      background: rgba(99, 183, 132, 0.09);
    }
    .flash-error {
      border-color: rgba(207, 108, 92, 0.38);
      background: rgba(207, 108, 92, 0.09);
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.5;
      color: #efe7d8;
      background: rgba(8, 7, 6, 0.55);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 16px;
      padding: 16px;
      max-height: 480px;
      overflow: auto;
    }
    @media (max-width: 720px) {
      .shell { width: min(100% - 16px, 100%); margin: 16px auto; }
      .hero { padding: 18px; }
      .card { padding: 16px; }
      dl { grid-template-columns: 1fr; }
      .switcher { grid-template-columns: 1fr; }
    }
    @media (prefers-reduced-motion: reduce) {
      *,
      *::before,
      *::after {
        animation: none !important;
        transition: none !important;
        scroll-behavior: auto !important;
      }
    }
  </style>
"""


DASHBOARD_SCRIPT = """
  <script>
    (() => {
      const pickers = document.querySelectorAll("[data-branch-picker]");
      const setExpanded = (picker, expanded) => {
        const trigger = picker.querySelector("[data-branch-trigger]");
        if (trigger) {
          trigger.setAttribute("aria-expanded", expanded ? "true" : "false");
        }
      };
      const closeAll = () => {
        for (const picker of pickers) {
          picker.classList.remove("is-open");
          setExpanded(picker, false);
        }
      };

      for (const picker of pickers) {
        const trigger = picker.querySelector("[data-branch-trigger]");
        const hiddenInput = picker.querySelector("[data-branch-input]");
        const valueLabel = picker.querySelector("[data-branch-value]");
        const options = picker.querySelectorAll("[data-branch-option]");
        if (!(trigger instanceof HTMLButtonElement) || !(hiddenInput instanceof HTMLInputElement) || !(valueLabel instanceof HTMLElement)) {
          continue;
        }

        const open = () => {
          if (trigger.disabled) {
            return;
          }
          closeAll();
          picker.classList.add("is-open");
          setExpanded(picker, true);
        };
        const close = () => {
          picker.classList.remove("is-open");
          setExpanded(picker, false);
        };
        const syncSelected = (nextValue) => {
          hiddenInput.value = nextValue;
          for (const option of options) {
            const isSelected = option.getAttribute("data-value") === nextValue;
            option.classList.toggle("is-selected", isSelected);
            option.setAttribute("aria-selected", isSelected ? "true" : "false");
            if (isSelected) {
              valueLabel.textContent = option.getAttribute("data-label") || nextValue;
            }
          }
        };

        const toggle = () => {
          if (picker.classList.contains("is-open")) {
            close();
          } else {
            open();
          }
        };

        trigger.addEventListener("pointerdown", (event) => {
          if (event.button !== 0) {
            return;
          }
          event.preventDefault();
          toggle();
          trigger.focus();
        });

        trigger.addEventListener("keydown", (event) => {
          if (event.key === "Escape") {
            close();
            return;
          }
          if (event.key === "Tab") {
            close();
            return;
          }
          if (event.key === " " || event.key === "Enter") {
            event.preventDefault();
            toggle();
            return;
          }
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            open();
          }
        });

        for (const option of options) {
          option.addEventListener("pointerdown", (event) => {
            event.preventDefault();
          });
          option.addEventListener("click", () => {
            syncSelected(option.getAttribute("data-value") || "");
            close();
            trigger.focus();
          });
        }

        picker.addEventListener("focusout", () => {
          window.setTimeout(() => {
            if (!picker.contains(document.activeElement)) {
              close();
            }
          }, 0);
        });

        syncSelected(hiddenInput.value);
      }

      document.addEventListener("pointerdown", (event) => {
        if (!(event.target instanceof Element) || event.target.closest("[data-branch-picker]")) {
          return;
        }
        closeAll();
      });
    })();
  </script>
"""


def render_login_page(data: LoginPageData) -> str:
    error_block = ""
    if data.error:
        error_block = f'<div class="flash flash-error">{html.escape(data.error)}</div>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(data.title)}</title>
{LOGIN_STYLES}
</head>
<body>
  <main class="panel">
    <h1>{html.escape(data.title)}</h1>
    <p>Local control panel for the bot. Access is available only through the SSH tunnel and the panel password.</p>
    {error_block}
    <form method="post" action="/login">
      <label for="password">Panel password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required>
      <button type="submit">Sign in</button>
    </form>
  </main>
</body>
</html>"""


def render_dashboard_page(data: DashboardPageData) -> str:
    active_state = data.service_data.get("ActiveState", "unknown")
    sub_state = data.service_data.get("SubState", "unknown")
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
            f"<pre>{html.escape(data.flash.output or 'Done.')}</pre>"
            "</section>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="{DASHBOARD_REFRESH_SECONDS}">
  <title>Warlords Bot Panel</title>
{DASHBOARD_STYLES}
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Bot Control Room</p>
        <h1>Warlords Panel</h1>
        <p>{html.escape(HERO_DESCRIPTION)}</p>
      </div>
      <div class="hero-actions">
        <a href="/">Refresh view</a>
        <form method="post" action="/logout">
          <button type="submit">Sign out</button>
        </form>
      </div>
    </section>

    <section class="grid">
      <article class="card">
        <h2>Service</h2>
        <div class="status-pill {status_class}">{html.escape(data.service_data.get("status_text", "Unknown"))}</div>
        <dl>
          <dt>Systemd unit</dt>
          <dd>{html.escape(data.service_data.get("Id", data.service_name))}</dd>
          <dt>Main PID</dt>
          <dd>{html.escape(data.service_data.get("MainPID", "0"))}</dd>
          <dt>Active since</dt>
          <dd>{html.escape(data.service_data.get("ActiveEnterTimestamp", "n/a"))}</dd>
          <dt>Unit file</dt>
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
          <dt>Current branch</dt>
          <dd>{html.escape(data.git_data.current_branch)}</dd>
          <dt>Upstream</dt>
          <dd>{html.escape(data.git_data.upstream or "not set")}</dd>
          <dt>Tracking</dt>
          <dd>{html.escape(data.tracking_status)}</dd>
          <dt>Worktree</dt>
          <dd>{html.escape(data.git_data.worktree_status)}</dd>
          <dt>Commit</dt>
          <dd>{html.escape(data.git_data.commit)}</dd>
          <dt>Latest message</dt>
          <dd>{html.escape(data.git_data.subject)}</dd>
        </dl>
      </article>
    </section>

    <section class="card section-actions" style="margin-top: 16px;">
      <h2>Service Actions</h2>
      <div class="actions">
        <form method="post" action="/action">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="start">
          <button type="submit" {start_disabled}>Start</button>
        </form>
        <form method="post" action="/action">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="restart">
          <button type="submit" class="secondary">Restart</button>
        </form>
        <form method="post" action="/action">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="stop">
          <button type="submit" class="danger" {stop_disabled}>Stop</button>
        </form>
        <form method="post" action="/action">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="update">
          <button type="submit">Update current branch</button>
        </form>
      </div>
      <p class="hint">Update uses the current git branch, runs fetch and pull --ff-only, refreshes dependencies, and restarts the bot service.</p>
    </section>

    <section class="card section-branches" style="margin-top: 16px;">
      <h2>Branches</h2>
      <div class="actions" style="margin-bottom: 12px;">
        <form method="post" action="/action">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="fetch">
          <button type="submit" class="secondary">Fetch refs</button>
        </form>
      </div>
      <form method="post" action="/action" class="switcher">
        <div>
{branch_picker}
        </div>
        <div class="switcher-submit">
          <input type="hidden" name="csrf_token" value="{html.escape(data.csrf_token)}">
          <input type="hidden" name="action" value="switch_branch">
          <button type="submit" class="secondary" {switch_disabled}>Switch branch</button>
        </div>
      </form>
      <p class="hint">After switching, the panel updates the selected branch, refreshes dependencies, and restarts the bot service.</p>
    </section>

    {flash_block}

    <section class="card log-card">
      <h2>Recent Logs</h2>
      <pre>{html.escape(data.logs)}</pre>
    </section>
  </main>
{DASHBOARD_SCRIPT}
</body>
</html>"""


def build_branch_picker(current_branch: str, branches: tuple[str, ...]) -> str:
    current_value = current_branch if current_branch in branches else (branches[0] if branches else "")
    current_label = current_value or "No remote branches"
    disabled_attr = " disabled" if not branches else ""
    options: list[str] = []

    if not branches:
        options.append(
            '<button type="button" class="branch-picker__option is-selected" '
            'data-branch-option data-value="" data-label="No remote branches" '
            'aria-selected="true" disabled>No remote branches</button>'
        )
    else:
        for branch in branches:
            selected = branch == current_value
            selected_class = " is-selected" if selected else ""
            selected_attr = "true" if selected else "false"
            escaped_branch = html.escape(branch)
            options.append(
                f'<button type="button" class="branch-picker__option{selected_class}" '
                f'data-branch-option data-value="{escaped_branch}" data-label="{escaped_branch}" '
                f'aria-selected="{selected_attr}">{escaped_branch}</button>'
            )

    return (
        '          <div class="branch-picker" data-branch-picker>\n'
        '            <span class="branch-picker__label">Remote branch</span>\n'
        f'            <input type="hidden" name="branch" value="{html.escape(current_value)}" data-branch-input>\n'
        f'            <button type="button" class="branch-picker__trigger" data-branch-trigger aria-expanded="false" aria-haspopup="listbox"{disabled_attr}>\n'
        f'              <span class="branch-picker__value" data-branch-value>{html.escape(current_label)}</span>\n'
        '              <span class="branch-picker__caret" aria-hidden="true"></span>\n'
        '            </button>\n'
        f'            <div class="branch-picker__menu" data-branch-menu role="listbox">{"".join(options)}</div>\n'
        '          </div>'
    )
