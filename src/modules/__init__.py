from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.module import BotModule


DEFAULT_MODULES = (
    "tickets",
    "welcome",
    "rules",
    "roles",
    "kompromat",
    "presence",
    "maintenance",
)


def get_modules(enabled_modules: str | None = None) -> list["BotModule"]:
    if enabled_modules:
        requested = [name.strip() for name in enabled_modules.split(",") if name.strip()]
    else:
        requested = list(DEFAULT_MODULES)

    modules: list["BotModule"] = []
    for module_name in requested:
        if module_name not in DEFAULT_MODULES:
            supported = ", ".join(DEFAULT_MODULES)
            raise ValueError(f"Неизвестный модуль {module_name!r}. Доступны: {supported}.")
        package = importlib.import_module(f"modules.{module_name}")
        if not hasattr(package, "build_module"):
            raise AttributeError(f"modules.{module_name} must expose build_module()")
        modules.append(package.build_module())

    return modules
