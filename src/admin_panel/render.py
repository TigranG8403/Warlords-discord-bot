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
    discord_login_url: str | None = None
    password_enabled: bool = False


@dataclass(frozen=True)
class CurrentUserView:
    user_id: str
    display_name: str
    username: str
    avatar_url: str | None


@dataclass(frozen=True)
class AllowedUserView:
    user_id: str
    display_name: str
    username: str
    avatar_url: str | None
    removable: bool = True


@dataclass(frozen=True)
class DashboardPageData:
    csrf_token: str
    service_name: str
    service_data: dict[str, str]
    git_data: GitSnapshot
    tracking_status: str
    logs: str
    flash: FlashMessage | None
    current_user: CurrentUserView | None
    allowed_users: tuple[AllowedUserView, ...]
    discord_auth_enabled: bool


DASHBOARD_REFRESH_SECONDS = 240
HERO_DESCRIPTION = "Управление Discord-ботом, сервисом и git-ветками в одном центре управления."


LOGIN_STYLES = """
  <style>
    :root {
      color-scheme: dark;
      --wl-bg: #0d0a12;
      --wl-bg-soft: #171320;
      --wl-surface: rgba(24, 19, 34, 0.78);
      --wl-surface-strong: rgba(28, 22, 40, 0.92);
      --wl-surface-soft: rgba(255, 255, 255, 0.04);
      --wl-border: rgba(255, 255, 255, 0.08);
      --wl-border-strong: rgba(242, 194, 123, 0.22);
      --wl-text: #f6efe5;
      --wl-text-soft: #c7becf;
      --wl-blue: #7d95ca;
      --wl-gold: #f2c27b;
      --wl-gold-soft: #ffd39a;
      --wl-copper: #bf7448;
      --wl-danger: #d76c7b;
      --wl-shadow: 0 32px 90px rgba(0, 0, 0, 0.42);
    }
    * { box-sizing: border-box; }
    @keyframes fade-rise {
      from { opacity: 0; transform: translateY(14px) scale(0.985); }
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
      font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
      letter-spacing: 0.015em;
      color: var(--wl-text);
      background:
        radial-gradient(circle at 14% 14%, rgba(125, 149, 202, 0.18), transparent 28%),
        radial-gradient(circle at 84% 12%, rgba(242, 194, 123, 0.12), transparent 22%),
        radial-gradient(circle at 50% 115%, rgba(191, 116, 72, 0.15), transparent 28%),
        linear-gradient(180deg, var(--wl-bg-soft) 0%, var(--wl-bg) 100%);
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
      width: 300px;
      height: 300px;
      top: -2%;
      left: 4%;
      background: rgba(125, 149, 202, 0.22);
    }
    body::after {
      width: 260px;
      height: 260px;
      right: -2%;
      bottom: 6%;
      background: rgba(242, 194, 123, 0.18);
      animation-delay: -5s;
    }
    .panel {
      width: min(100%, 420px);
      position: relative;
      border: 1px solid var(--wl-border);
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0)),
        linear-gradient(180deg, var(--wl-surface-strong), rgba(16, 12, 24, 0.96));
      border-radius: 28px;
      padding: 30px;
      box-shadow: var(--wl-shadow);
      animation: fade-rise 420ms ease both;
      backdrop-filter: blur(16px);
      overflow: hidden;
    }
    .panel::before {
      content: "";
      position: absolute;
      inset: 0 0 auto 0;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(242, 194, 123, 0.46), transparent);
    }
    h1 {
      margin: 0 0 12px;
      font-size: 30px;
      letter-spacing: -0.03em;
      text-transform: uppercase;
      color: #fff7ee;
    }
    p {
      margin: 0 0 22px;
      color: var(--wl-text-soft);
      line-height: 1.5;
    }
    label {
      display: block;
      margin-bottom: 8px;
      color: var(--wl-text-soft);
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    input {
      width: 100%;
      border: 1px solid var(--wl-border);
      background: rgba(13, 10, 18, 0.88);
      color: var(--wl-text);
      border-radius: 16px;
      padding: 14px 16px;
      font: inherit;
      margin-bottom: 16px;
      transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease, background 180ms ease;
    }
    input:focus {
      outline: none;
      border-color: var(--wl-border-strong);
      background: rgba(18, 14, 26, 0.94);
      box-shadow: 0 0 0 4px rgba(242, 194, 123, 0.1);
      transform: translateY(-1px);
    }
    button {
      width: 100%;
      border: 0;
      border-radius: 16px;
      padding: 14px 16px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      color: #1b1208;
      background: linear-gradient(180deg, var(--wl-gold-soft), var(--wl-gold));
      transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease;
    }
    button:hover {
      transform: translateY(-1px);
      box-shadow: 0 16px 32px rgba(242, 194, 123, 0.22);
      filter: brightness(1.03);
    }
    .login-actions {
      display: grid;
      gap: 14px;
    }
    .discord-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      width: 100%;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      padding: 14px 16px;
      text-decoration: none;
      font-weight: 700;
      color: #f6f7fb;
      background: linear-gradient(180deg, #839de1, #5f74d2);
      transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease;
    }
    .discord-button:hover {
      transform: translateY(-1px);
      box-shadow: 0 16px 34px rgba(125, 149, 202, 0.26);
      filter: brightness(1.03);
    }
    .divider {
      display: flex;
      align-items: center;
      gap: 12px;
      color: var(--wl-text-soft);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
      margin: 4px 0;
    }
    .divider::before,
    .divider::after {
      content: "";
      height: 1px;
      flex: 1;
      background: rgba(255, 255, 255, 0.08);
    }
    .flash {
      margin-bottom: 16px;
      border-radius: 16px;
      padding: 12px 14px;
      border: 1px solid rgba(215, 108, 123, 0.45);
      background: rgba(215, 108, 123, 0.12);
      color: #ffd7de;
      animation: fade-rise 280ms ease both;
    }
  </style>
"""


DASHBOARD_STYLES = """
  <style>
    :root {
      color-scheme: dark;
      --wl-bg: #0d0a12;
      --wl-bg-soft: #171320;
      --wl-surface: rgba(24, 19, 34, 0.78);
      --wl-surface-strong: rgba(28, 22, 40, 0.9);
      --wl-surface-soft: rgba(255, 255, 255, 0.035);
      --wl-border: rgba(255, 255, 255, 0.08);
      --wl-border-strong: rgba(242, 194, 123, 0.22);
      --wl-text: #f6efe5;
      --wl-text-soft: #c7becf;
      --wl-blue: #7d95ca;
      --wl-gold: #f2c27b;
      --wl-copper: #bf7448;
      --wl-success: #6dbd89;
      --wl-danger: #d76c7b;
      --wl-shadow-lg: 0 22px 60px rgba(0, 0, 0, 0.34);
      --wl-shadow-xl: 0 32px 90px rgba(0, 0, 0, 0.42);
      --mono: "Consolas", "SFMono-Regular", monospace;
    }
    * { box-sizing: border-box; }
    @keyframes fade-rise {
      from { opacity: 0; transform: translateY(16px) scale(0.985); }
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
      color: var(--wl-text);
      font-family: "Segoe UI Variable", "Segoe UI", system-ui, sans-serif;
      letter-spacing: 0.015em;
      background:
        radial-gradient(circle at 14% 14%, rgba(125, 149, 202, 0.18), transparent 28%),
        radial-gradient(circle at 84% 12%, rgba(242, 194, 123, 0.12), transparent 22%),
        radial-gradient(circle at 50% 115%, rgba(191, 116, 72, 0.16), transparent 30%),
        linear-gradient(180deg, var(--wl-bg-soft) 0%, var(--wl-bg) 100%);
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
      width: 30rem;
      height: 30rem;
      top: -10rem;
      left: -8rem;
      background: radial-gradient(circle, rgba(125, 149, 202, 0.4) 0%, rgba(125, 149, 202, 0) 70%);
    }
    body::after {
      width: 34rem;
      height: 34rem;
      right: -10rem;
      bottom: -16rem;
      background: radial-gradient(circle, rgba(242, 194, 123, 0.28) 0%, rgba(191, 116, 72, 0) 74%);
      animation-delay: -6s;
    }
    .shell {
      width: min(1180px, calc(100% - 32px));
      margin: 28px auto 36px;
      position: relative;
      z-index: 1;
    }
    .hero,
    .card {
      animation: fade-rise 420ms ease both;
    }
    .hero {
      display: flex;
      flex-wrap: wrap;
      gap: 18px;
      align-items: flex-end;
      justify-content: space-between;
      margin-bottom: 18px;
      padding: 24px 26px;
      border: 1px solid var(--wl-border);
      border-radius: 28px;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.03), rgba(255, 255, 255, 0)),
        linear-gradient(180deg, var(--wl-surface-strong), rgba(16, 12, 24, 0.96));
      backdrop-filter: blur(16px);
      box-shadow: var(--wl-shadow-lg);
      overflow: hidden;
      position: relative;
    }
    .hero::before,
    .card::before {
      content: "";
      position: absolute;
      inset: 0 0 auto 0;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(242, 194, 123, 0.44), transparent);
      pointer-events: none;
    }
    .grid .card:nth-child(1) { animation-delay: 80ms; }
    .grid .card:nth-child(2) { animation-delay: 140ms; }
    .section-actions { animation-delay: 200ms; }
    .section-branches { animation-delay: 260ms; }
    .log-card { margin-top: 16px; animation-delay: 320ms; }
    .eyebrow {
      margin: 0 0 8px;
      color: var(--wl-text-soft);
      letter-spacing: 0.14em;
      text-transform: uppercase;
      font-size: 12px;
    }
    h1 {
      margin: 0;
      font-size: clamp(30px, 4vw, 46px);
      letter-spacing: -0.03em;
      text-transform: uppercase;
      color: #fff7ee;
    }
    .hero p {
      margin: 12px 0 0;
      max-width: 680px;
      color: var(--wl-text-soft);
      line-height: 1.6;
    }
    .hero-actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      justify-content: flex-end;
    }
    .hero-actions a,
    .hero-actions button {
      border: 1px solid var(--wl-border);
      background: rgba(255, 255, 255, 0.03);
      color: var(--wl-text);
      border-radius: 999px;
      padding: 10px 16px;
      font: inherit;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      transition: transform 180ms ease, border-color 180ms ease, background 180ms ease, box-shadow 180ms ease;
    }
    .hero-actions a:hover,
    .hero-actions button:hover {
      transform: translateY(-1px);
      border-color: rgba(242, 194, 123, 0.28);
      background: rgba(242, 194, 123, 0.08);
      box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18);
    }
    .hero-actions form { margin: 0; }
    .user-chip {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      padding: 8px 10px 8px 8px;
      border-radius: 999px;
      border: 1px solid var(--wl-border);
      background: rgba(13, 10, 18, 0.68);
      min-width: 0;
      max-width: min(100%, 320px);
    }
    .avatar {
      width: 38px;
      height: 38px;
      border-radius: 50%;
      object-fit: cover;
      display: block;
      flex: 0 0 auto;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(242, 194, 123, 0.14);
      box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.025);
    }
    .avatar-fallback {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 38px;
      height: 38px;
      border-radius: 50%;
      flex: 0 0 auto;
      background: linear-gradient(180deg, rgba(125, 149, 202, 0.52), rgba(191, 116, 72, 0.38));
      color: #fff4e0;
      font-size: 15px;
      font-weight: 700;
      border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .user-meta {
      min-width: 0;
      display: grid;
      gap: 2px;
    }
    .user-meta strong,
    .user-meta span {
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .user-meta strong { font-size: 14px; color: var(--wl-text); }
    .user-meta span { font-size: 12px; color: var(--wl-text-soft); }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
    }
    .card {
      position: relative;
      border: 1px solid var(--wl-border);
      border-radius: 24px;
      padding: 20px;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0)),
        var(--wl-surface);
      backdrop-filter: blur(16px);
      overflow: visible;
      transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }
    .card:hover {
      transform: translateY(-2px);
      border-color: rgba(242, 194, 123, 0.22);
      box-shadow: var(--wl-shadow-lg);
    }
    .card h2 {
      margin: 0 0 16px;
      font-size: 14px;
      color: var(--wl-text-soft);
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
      border: 1px solid var(--wl-border);
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
    .status-running::before { background: var(--wl-success); animation: pulse-dot 1.8s ease-in-out infinite; }
    .status-stopped::before { background: var(--wl-danger); }
    dl {
      display: grid;
      grid-template-columns: minmax(120px, 160px) 1fr;
      gap: 10px 12px;
      margin: 0;
    }
    dt { color: var(--wl-text-soft); font-size: 14px; }
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
      border-radius: 16px;
      padding: 14px 16px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      color: #1a1208;
      background: linear-gradient(180deg, #ffd39a, var(--wl-gold));
      transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease, opacity 180ms ease;
    }
    .actions button:hover,
    .switcher-submit button:hover {
      transform: translateY(-1px);
      box-shadow: 0 14px 28px rgba(242, 194, 123, 0.16);
      filter: brightness(1.03);
    }
    .actions button.danger {
      color: #fff4f2;
      background: linear-gradient(180deg, #ec8ea0, var(--wl-danger));
    }
    .actions button.secondary,
    .switcher-submit button.secondary {
      color: var(--wl-text);
      background: linear-gradient(180deg, rgba(125, 149, 202, 0.14), rgba(28, 22, 40, 0.92));
      border: 1px solid var(--wl-border);
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
    .hint { margin: 14px 0 0; color: var(--wl-text-soft); line-height: 1.5; }
    .access-grid {
      display: grid;
      grid-template-columns: minmax(260px, 360px) 1fr;
      gap: 16px;
      align-items: start;
    }
    .access-form {
      display: grid;
      gap: 12px;
    }
    .access-form label {
      display: block;
      color: var(--wl-text-soft);
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .access-form input {
      width: 100%;
      border: 1px solid var(--wl-border);
      border-radius: 16px;
      background: rgba(13, 10, 18, 0.82);
      color: var(--wl-text);
      padding: 13px 14px;
      font: inherit;
    }
    .access-form input:focus {
      outline: none;
      border-color: rgba(242, 194, 123, 0.32);
      box-shadow: 0 0 0 3px rgba(242, 194, 123, 0.08);
    }
    .access-list {
      display: grid;
      gap: 12px;
    }
    .access-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 14px;
      border-radius: 18px;
      border: 1px solid var(--wl-border);
      background: rgba(13, 10, 18, 0.52);
    }
    .access-item-user {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .access-item-meta {
      min-width: 0;
      display: grid;
      gap: 2px;
    }
    .access-item-meta strong,
    .access-item-meta span {
      display: block;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .access-item-meta strong { font-size: 14px; color: var(--wl-text); }
    .access-item-meta span {
      font-size: 12px;
      color: var(--wl-text-soft);
      font-family: var(--mono);
    }
    .inline-button {
      width: auto;
      min-width: 120px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      width: fit-content;
      padding: 5px 9px;
      border-radius: 999px;
      border: 1px solid var(--wl-border);
      background: rgba(242, 194, 123, 0.08);
      color: #f0debe;
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
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
      color: var(--wl-text-soft);
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
      color: var(--wl-text-soft);
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
      border: 1px solid var(--wl-border);
      border-radius: 16px;
      padding: 14px 16px;
      font: inherit;
      color: var(--wl-text);
      background: rgba(13, 10, 18, 0.84);
      transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease, background 180ms ease;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
    }
    .branch-picker__trigger:hover {
      transform: translateY(-1px);
      border-color: rgba(242, 194, 123, 0.3);
      background: rgba(18, 14, 26, 0.92);
    }
    .branch-picker__trigger:focus-visible {
      outline: none;
      border-color: rgba(242, 194, 123, 0.3);
      box-shadow: 0 0 0 3px rgba(242, 194, 123, 0.08);
    }
    .branch-picker__trigger[aria-expanded="true"] {
      border-color: rgba(242, 194, 123, 0.34);
      background: rgba(20, 16, 29, 0.96);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02), 0 12px 24px rgba(0, 0, 0, 0.16);
    }
    .branch-picker__value {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      text-align: left;
      color: var(--wl-text);
      font-weight: 700;
      letter-spacing: 0.01em;
      text-shadow: none;
    }
    .branch-picker__caret {
      display: inline-block;
      width: 10px;
      height: 10px;
      border-right: 2px solid var(--wl-text);
      border-bottom: 2px solid var(--wl-text);
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
      border: 1px solid var(--wl-border);
      border-radius: 18px;
      background: linear-gradient(180deg, rgba(24, 19, 34, 0.985), rgba(15, 11, 22, 0.985));
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
      color: var(--wl-text);
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
      border-color: rgba(242, 194, 123, 0.22);
      background: rgba(242, 194, 123, 0.08);
    }
    .branch-picker__option.is-selected {
      border-color: rgba(242, 194, 123, 0.2);
      color: #fff3df;
      background: linear-gradient(180deg, rgba(125, 149, 202, 0.16), rgba(191, 116, 72, 0.2));
      box-shadow: inset 0 1px 0 rgba(255, 244, 224, 0.03);
    }
    .branch-picker__option.is-selected:hover {
      border-color: rgba(242, 194, 123, 0.32);
      color: #fff7ea;
      background: linear-gradient(180deg, rgba(125, 149, 202, 0.22), rgba(191, 116, 72, 0.24));
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
      border-color: rgba(109, 189, 137, 0.38);
      background: rgba(109, 189, 137, 0.09);
    }
    .flash-error {
      border-color: rgba(215, 108, 123, 0.38);
      background: rgba(215, 108, 123, 0.09);
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: var(--mono);
      font-size: 12px;
      line-height: 1.5;
      color: #efe7d8;
      background: rgba(13, 10, 18, 0.72);
      border: 1px solid var(--wl-border);
      border-radius: 18px;
      padding: 16px;
      max-height: 480px;
      overflow: auto;
    }
    @media (max-width: 720px) {
      .shell { width: min(100% - 16px, 100%); margin: 16px auto; }
      .hero { padding: 20px; }
      .card { padding: 18px; }
      dl { grid-template-columns: 1fr; }
      .access-grid { grid-template-columns: 1fr; }
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

    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="{DASHBOARD_REFRESH_SECONDS}">
  <title>Warlords Bot</title>
{DASHBOARD_STYLES}
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Warlords Bot Control</p>
        <h1>Warlords Bot</h1>
        <p>{html.escape(HERO_DESCRIPTION)}</p>
      </div>
      <div class="hero-actions">
        {user_chip}
        <a href="/">Обновить</a>
        <form method="post" action="/logout">
          <button type="submit">Выйти</button>
        </form>
      </div>
    </section>

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

    {flash_block}
    {access_section}

    <section class="card log-card">
      <h2>Последние логи</h2>
      <pre>{html.escape(data.logs)}</pre>
    </section>
  </main>
{DASHBOARD_SCRIPT}
</body>
</html>"""


def build_branch_picker(current_branch: str, branches: tuple[str, ...]) -> str:
    current_value = current_branch if current_branch in branches else (branches[0] if branches else "")
    current_label = current_value or "Нет удалённых веток"
    disabled_attr = " disabled" if not branches else ""
    options: list[str] = []

    if not branches:
        options.append(
            '<button type="button" class="branch-picker__option is-selected" '
            'data-branch-option data-value="" data-label="Нет удалённых веток" '
            'aria-selected="true" disabled>Нет удалённых веток</button>'
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
        '            <span class="branch-picker__label">Удалённая ветка</span>\n'
        f'            <input type="hidden" name="branch" value="{html.escape(current_value)}" data-branch-input>\n'
        f'            <button type="button" class="branch-picker__trigger" data-branch-trigger aria-expanded="false" aria-haspopup="listbox"{disabled_attr}>\n'
        f'              <span class="branch-picker__value" data-branch-value>{html.escape(current_label)}</span>\n'
        '              <span class="branch-picker__caret" aria-hidden="true"></span>\n'
        '            </button>\n'
        f'            <div class="branch-picker__menu" data-branch-menu role="listbox">{"".join(options)}</div>\n'
        '          </div>'
    )


def render_avatar(label: str, avatar_url: str | None) -> str:
    if avatar_url:
        return f'<img class="avatar" src="{html.escape(avatar_url)}" alt="{html.escape(label)} avatar">'
    initial = (label[:1] or "?").upper()
    return f'<span class="avatar-fallback" aria-hidden="true">{html.escape(initial)}</span>'
