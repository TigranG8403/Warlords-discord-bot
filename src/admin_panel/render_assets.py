from __future__ import annotations

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
    .view-tabs {
      display: inline-flex;
      gap: 8px;
      margin-top: 16px;
      padding: 6px;
      border: 1px solid var(--wl-border);
      border-radius: 999px;
      background: rgba(13, 10, 18, 0.46);
      backdrop-filter: blur(12px);
    }
    .view-tab {
      border: 0;
      border-radius: 999px;
      padding: 10px 16px;
      font: inherit;
      font-weight: 700;
      letter-spacing: 0.02em;
      color: var(--wl-text-soft);
      background: transparent;
      cursor: pointer;
      transition: transform 180ms ease, background 180ms ease, color 180ms ease, box-shadow 180ms ease;
    }
    .view-tab:hover {
      transform: translateY(-1px);
      color: #fff6e8;
      background: rgba(255, 255, 255, 0.04);
    }
    .view-tab.is-active {
      color: #1a1208;
      background: linear-gradient(180deg, #ffd39a, var(--wl-gold));
      box-shadow: 0 12px 24px rgba(242, 194, 123, 0.18);
    }
    .dashboard-tab {
      display: none;
    }
    .dashboard-tab.is-active {
      display: block;
      animation: fade-rise 280ms ease both;
    }
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
    .summary-grid,
    .module-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
    }
    .summary-card,
    .module-card {
      position: relative;
      border: 1px solid var(--wl-border);
      border-radius: 22px;
      padding: 18px;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0)),
        rgba(13, 10, 18, 0.54);
      overflow: hidden;
    }
    .summary-card::before,
    .module-card::before {
      content: "";
      position: absolute;
      inset: 0 0 auto 0;
      height: 1px;
      background: linear-gradient(90deg, transparent, rgba(242, 194, 123, 0.36), transparent);
    }
    .summary-card strong,
    .module-card strong {
      display: block;
      font-size: 14px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--wl-text-soft);
      margin-bottom: 10px;
    }
    .summary-card b {
      display: block;
      font-size: 30px;
      letter-spacing: -0.04em;
      color: #fff7ee;
    }
    .summary-card span {
      color: var(--wl-text-soft);
    }
    .module-card p {
      margin: 0 0 12px;
      color: var(--wl-text-soft);
    }
    .module-card code {
      display: inline-flex;
      width: fit-content;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: rgba(255, 255, 255, 0.04);
      color: #f5e4c8;
      font-size: 12px;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .summary-list {
      display: grid;
      gap: 10px;
      margin: 0;
    }
    .summary-list div {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      padding-bottom: 10px;
    }
    .summary-list div:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }
    .summary-list dt,
    .summary-list dd {
      margin: 0;
      font-size: 13px;
    }
    .summary-list dd {
      color: #fff2dd;
      font-family: var(--mono);
      text-align: right;
    }
    .player-shell {
      display: grid;
      gap: 16px;
    }
    .player-toolbar {
      display: grid;
      gap: 12px;
      margin-bottom: 16px;
    }
    .player-search-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(180px, 220px) auto;
      gap: 12px;
      align-items: end;
    }
    .player-toolbar label,
    .player-stack-form label {
      display: block;
      color: var(--wl-text-soft);
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .player-list {
      display: grid;
      gap: 12px;
    }
    .player-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: center;
      padding: 16px;
      border-radius: 20px;
      border: 1px solid var(--wl-border);
      background: rgba(13, 10, 18, 0.52);
      text-decoration: none;
      color: inherit;
      transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease, background 180ms ease;
    }
    .player-row:hover,
    .player-row.is-selected {
      transform: translateY(-1px);
      border-color: rgba(242, 194, 123, 0.24);
      box-shadow: 0 18px 32px rgba(0, 0, 0, 0.16);
      background: rgba(19, 15, 28, 0.8);
    }
    .player-row-main {
      min-width: 0;
      display: grid;
      gap: 8px;
    }
    .player-row-head {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      min-width: 0;
    }
    .player-row-head strong {
      font-size: 16px;
      color: #fff7ee;
    }
    .player-row-meta,
    .player-row-side {
      display: grid;
      gap: 6px;
      min-width: 0;
    }
    .player-row-meta span,
    .player-row-side span {
      color: var(--wl-text-soft);
      font-size: 13px;
      word-break: break-word;
    }
    .player-row-side {
      justify-items: end;
      text-align: right;
    }
    .player-tag {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      width: fit-content;
      padding: 5px 10px;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: rgba(255, 255, 255, 0.04);
      color: #f0debe;
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .player-tag-auto {
      border-color: rgba(125, 149, 202, 0.26);
      background: rgba(125, 149, 202, 0.12);
      color: #d8e2ff;
    }
    .player-tag-allowed {
      border-color: rgba(109, 189, 137, 0.26);
      background: rgba(109, 189, 137, 0.12);
      color: #dff7e7;
    }
    .player-tag-blocked {
      border-color: rgba(215, 108, 123, 0.28);
      background: rgba(215, 108, 123, 0.12);
      color: #ffdbe3;
    }
    .player-tag-muted {
      color: var(--wl-text-soft);
      border-color: var(--wl-border);
      background: rgba(255, 255, 255, 0.02);
    }
    .player-tag-warn {
      border-color: rgba(242, 194, 123, 0.28);
      background: rgba(242, 194, 123, 0.12);
      color: #fff0d4;
    }
    .player-tag-online {
      border-color: rgba(109, 189, 137, 0.32);
      background: rgba(109, 189, 137, 0.16);
      color: #e4ffe9;
      box-shadow: inset 0 0 0 1px rgba(109, 189, 137, 0.12);
    }
    .player-detail-grid {
      display: grid;
      gap: 14px;
    }
    .player-detail-card {
      display: grid;
      gap: 14px;
      padding: 18px;
      border-radius: 20px;
      border: 1px solid var(--wl-border);
      background: rgba(13, 10, 18, 0.52);
    }
    .player-detail-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }
    .player-detail-head h3 {
      margin: 0;
      font-size: 22px;
      letter-spacing: -0.03em;
      color: #fff7ee;
    }
    .player-detail-head p {
      margin: 6px 0 0;
      color: var(--wl-text-soft);
    }
    .player-info-list {
      display: grid;
      gap: 10px;
    }
    .player-info-line {
      display: grid;
      grid-template-columns: minmax(120px, 150px) 1fr;
      gap: 12px;
      align-items: start;
      padding-bottom: 10px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    .player-info-line:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }
    .player-info-line strong {
      color: var(--wl-text-soft);
      font-size: 13px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .player-info-line span,
    .player-info-line a {
      color: var(--wl-text);
      word-break: break-word;
    }
    .player-actions {
      display: grid;
      gap: 14px;
    }
    .player-action-group {
      display: grid;
      gap: 12px;
    }
    .player-action-group h3 {
      margin: 0;
      font-size: 13px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--wl-text-soft);
    }
    .player-action-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
    }
    .player-inline-form,
    .player-stack-form {
      display: grid;
      gap: 10px;
      margin: 0;
    }
    .player-inline-form button,
    .player-stack-form button {
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
    .player-inline-form button:hover,
    .player-stack-form button:hover {
      transform: translateY(-1px);
      box-shadow: 0 14px 28px rgba(242, 194, 123, 0.16);
      filter: brightness(1.03);
    }
    .player-inline-form button.secondary,
    .player-stack-form button.secondary {
      color: var(--wl-text);
      background: linear-gradient(180deg, rgba(125, 149, 202, 0.14), rgba(28, 22, 40, 0.92));
      border: 1px solid var(--wl-border);
    }
    .player-inline-form button.danger,
    .player-stack-form button.danger {
      color: #fff4f2;
      background: linear-gradient(180deg, #ec8ea0, var(--wl-danger));
    }
    .button-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      min-height: 48px;
      border-radius: 16px;
      border: 1px solid var(--wl-border);
      background: linear-gradient(180deg, rgba(125, 149, 202, 0.14), rgba(28, 22, 40, 0.92));
      color: var(--wl-text);
      font-weight: 700;
      text-decoration: none;
      transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease, background 180ms ease;
    }
    .button-link:hover {
      transform: translateY(-1px);
      border-color: rgba(242, 194, 123, 0.24);
      box-shadow: 0 14px 28px rgba(0, 0, 0, 0.14);
      background: linear-gradient(180deg, rgba(125, 149, 202, 0.2), rgba(28, 22, 40, 0.98));
    }
    .player-empty {
      padding: 28px;
      border-radius: 20px;
      border: 1px dashed rgba(255, 255, 255, 0.12);
      background: rgba(13, 10, 18, 0.32);
      color: var(--wl-text-soft);
      line-height: 1.7;
    }
    .player-empty strong {
      display: block;
      color: var(--wl-text);
      margin-bottom: 8px;
      letter-spacing: 0.04em;
    }
    .chart-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
    }
    .chart-card {
      display: grid;
      gap: 16px;
      overflow: hidden;
    }
    .chart-card-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      flex-wrap: wrap;
    }
    .chart-card-head h2 {
      margin: 0;
      font-size: 20px;
      letter-spacing: -0.03em;
      color: #fff7ee;
    }
    .chart-card-head p {
      margin: 6px 0 0;
      color: var(--wl-text-soft);
      line-height: 1.6;
    }
    .metric-pills {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }
    .metric-pill {
      display: inline-flex;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid rgba(109, 189, 137, 0.22);
      background: rgba(109, 189, 137, 0.12);
      color: #e8ffef;
      font-size: 12px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .metric-pill.secondary {
      border-color: rgba(255, 255, 255, 0.1);
      background: rgba(255, 255, 255, 0.04);
      color: var(--wl-text-soft);
    }
    .chart-shell {
      display: grid;
      gap: 10px;
    }
    .chart-svg {
      width: 100%;
      height: auto;
      border-radius: 18px;
      border: 1px solid rgba(255, 255, 255, 0.06);
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0)),
        rgba(13, 10, 18, 0.56);
      overflow: hidden;
    }
    .chart-guide line {
      stroke: rgba(255, 255, 255, 0.08);
      stroke-width: 1;
    }
    .chart-axis text {
      fill: var(--wl-text-soft);
      font-size: 12px;
      letter-spacing: 0.04em;
    }
    .chart-area {
      fill: rgba(125, 149, 202, 0.18);
    }
    .chart-line {
      fill: none;
      stroke: #8ea8f6;
      stroke-width: 3;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .chart-bar {
      rx: 10;
      ry: 10;
    }
    .chart-bar-login {
      fill: rgba(125, 149, 202, 0.88);
    }
    .chart-bar-link {
      fill: rgba(242, 194, 123, 0.9);
    }
    .chart-bar-ban {
      fill: rgba(215, 108, 123, 0.9);
    }
    .chart-foot {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      color: var(--wl-text-soft);
    }
    .chart-foot strong {
      color: var(--wl-text);
    }
    .chart-empty {
      padding: 28px;
      border-radius: 18px;
      border: 1px dashed rgba(255, 255, 255, 0.12);
      background: rgba(13, 10, 18, 0.32);
      color: var(--wl-text-soft);
      line-height: 1.6;
    }
    .bot-section-head {
      margin: 0 0 16px;
      color: var(--wl-text-soft);
      line-height: 1.6;
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
    .player-toolbar input,
    .player-toolbar select,
    .player-stack-form input,
    .player-stack-form textarea {
      width: 100%;
      border: 1px solid var(--wl-border);
      border-radius: 16px;
      background: rgba(13, 10, 18, 0.82);
      color: var(--wl-text);
      padding: 13px 14px;
      font: inherit;
    }
    .player-stack-form textarea {
      resize: vertical;
      min-height: 120px;
    }
    .access-form input:focus,
    .player-toolbar input:focus,
    .player-toolbar select:focus,
    .player-stack-form input:focus,
    .player-stack-form textarea:focus {
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
      .player-search-row { grid-template-columns: 1fr; }
      .player-row { grid-template-columns: 1fr; }
      .player-row-side { justify-items: start; text-align: left; }
      .player-info-line { grid-template-columns: 1fr; }
      .view-tabs {
        width: 100%;
      }
      .view-tab {
        flex: 1 1 0;
      }
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
      const tabButtons = document.querySelectorAll("[data-dashboard-tab]");
      const tabPanels = document.querySelectorAll("[data-tab-panel]");
      const panelRootSelector = "[data-discordauth-root]";
      const activateTab = (nextTab) => {
        for (const button of tabButtons) {
          button.classList.toggle("is-active", button.getAttribute("data-dashboard-tab") === nextTab);
        }
        for (const panel of tabPanels) {
          panel.classList.toggle("is-active", panel.getAttribute("data-tab-panel") === nextTab);
        }
        const nextUrl = new URL(window.location.href);
        nextUrl.searchParams.set("tab", nextTab);
        window.history.replaceState({}, "", nextUrl);
      };
      for (const button of tabButtons) {
        button.addEventListener("click", () => activateTab(button.getAttribute("data-dashboard-tab") || "server"));
      }
      const initialTab = (() => {
        const rawTab = new URL(window.location.href).searchParams.get("tab");
        return rawTab === "panel" || rawTab === "bot" ? "panel" : "server";
      })();
      activateTab(initialTab);
      const getPanelRoot = () => document.querySelector(panelRootSelector);
      const buildPanelUrls = (source) => {
        const pageUrl = new URL(source || window.location.href, window.location.href);
        pageUrl.searchParams.set("tab", "panel");
        pageUrl.searchParams.delete("partial");
        const fetchUrl = new URL(pageUrl.toString());
        fetchUrl.searchParams.set("partial", "discordauth");
        return { pageUrl, fetchUrl };
      };
      const replacePanelContent = async (source, historyMode = "replace") => {
        const panelRoot = getPanelRoot();
        if (!(panelRoot instanceof HTMLElement)) {
          return;
        }
        const { pageUrl, fetchUrl } = buildPanelUrls(source);
        panelRoot.setAttribute("aria-busy", "true");
        try {
          const response = await fetch(fetchUrl.toString(), {
            headers: { "X-Requested-With": "fetch" },
            credentials: "same-origin",
          });
          if (response.status === 401 || response.redirected) {
            window.location.assign("/login");
            return;
          }
          if (!response.ok) {
            return;
          }
          panelRoot.innerHTML = await response.text();
          bindDiscordAuthPanel();
          if (historyMode === "push") {
            window.history.pushState({}, "", pageUrl);
          } else if (historyMode === "replace") {
            window.history.replaceState({}, "", pageUrl);
          }
        } finally {
          panelRoot.removeAttribute("aria-busy");
        }
      };
      const submitDiscordAuthToolbar = (form, historyMode = "push") => {
        const nextUrl = new URL(form.getAttribute("action") || "/", window.location.href);
        const formData = new FormData(form);
        nextUrl.searchParams.set("tab", "panel");
        nextUrl.searchParams.delete("player_uuid");
        nextUrl.searchParams.delete("discordauth_search");
        nextUrl.searchParams.delete("discordauth_filter");
        for (const [key, rawValue] of formData.entries()) {
          if (typeof rawValue !== "string") {
            continue;
          }
          const value = rawValue.trim();
          if (!value || key === "player_uuid") {
            continue;
          }
          if (key === "discordauth_filter" && value === "all") {
            continue;
          }
          nextUrl.searchParams.set(key, value);
        }
        replacePanelContent(nextUrl.toString(), historyMode);
      };
      const bindDiscordAuthPanel = () => {
        const panelRoot = getPanelRoot();
        if (!(panelRoot instanceof HTMLElement) || panelRoot.dataset.bound === "true") {
          return;
        }
        panelRoot.dataset.bound = "true";
        panelRoot.addEventListener("click", (event) => {
          const target = event.target;
          if (!(target instanceof Element)) {
            return;
          }
          const link = target.closest("a.player-row, a.button-link");
          if (!(link instanceof HTMLAnchorElement)) {
            return;
          }
          if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
            return;
          }
          event.preventDefault();
          replacePanelContent(link.href, "push");
        });
        panelRoot.addEventListener("submit", (event) => {
          const form = event.target;
          if (!(form instanceof HTMLFormElement) || !form.matches("[data-discordauth-filter-form]")) {
            return;
          }
          event.preventDefault();
          submitDiscordAuthToolbar(form, "push");
        });
        panelRoot.addEventListener("change", (event) => {
          const target = event.target;
          if (!(target instanceof Element) || !target.matches("[data-discordauth-filter-input]")) {
            return;
          }
          const form = target.closest("form");
          if (form instanceof HTMLFormElement) {
            submitDiscordAuthToolbar(form, "push");
          }
        });
      };
      bindDiscordAuthPanel();
      window.addEventListener("popstate", () => {
        const nextUrl = new URL(window.location.href);
        const rawTab = nextUrl.searchParams.get("tab");
        const nextTab = rawTab === "panel" || rawTab === "bot" ? "panel" : "server";
        activateTab(nextTab);
        if (nextTab === "panel") {
          replacePanelContent(nextUrl.toString(), "none");
        }
      });
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
