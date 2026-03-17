from __future__ import annotations

import os
from pathlib import Path

try:
    from .server_handler import PanelHandler
    from .server_runtime import PanelServer
    from .server_shared import (
        CommandResult,
        ExpiringTokenStore,
        PanelConfig,
        SessionData,
        SessionStore,
        build_session_cookie,
        build_status_text,
        constant_time_equal,
        expire_session_cookie,
        load_config,
        load_dotenv_file,
        parse_key_value_output,
        trim_output,
    )
except ImportError:
    from admin_panel.server_handler import PanelHandler
    from admin_panel.server_runtime import PanelServer
    from admin_panel.server_shared import (
        CommandResult,
        ExpiringTokenStore,
        PanelConfig,
        SessionData,
        SessionStore,
        build_session_cookie,
        build_status_text,
        constant_time_equal,
        expire_session_cookie,
        load_config,
        load_dotenv_file,
        parse_key_value_output,
        trim_output,
    )


def main() -> None:
    env_path = os.getenv("PANEL_ENV_FILE")
    if env_path:
        load_dotenv_file(Path(env_path))

    config = load_config()
    server = PanelServer((config.host, config.port), PanelHandler, config)
    print(f"Warlords admin panel listening on http://{config.host}:{config.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
