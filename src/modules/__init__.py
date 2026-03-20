from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.module import BotModule


def _discover_module_names() -> list[str]:
    return sorted(
        module.name
        for module in pkgutil.iter_modules(__path__)
        if module.ispkg and not module.name.startswith("_")
    )


def get_modules(enabled_modules: str | None = None) -> list["BotModule"]:
    if enabled_modules:
        requested = [name.strip() for name in enabled_modules.split(",") if name.strip()]
    else:
        requested = _discover_module_names()

    modules: list["BotModule"] = []
    for module_name in requested:
        package = importlib.import_module(f"modules.{module_name}")
        if not hasattr(package, "build_module"):
            raise AttributeError(f"modules.{module_name} must expose build_module()")
        modules.append(package.build_module())

    return modules
