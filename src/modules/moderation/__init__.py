def build_module():
    from .module import build_module as _build_module

    return _build_module()


__all__ = ["build_module"]
