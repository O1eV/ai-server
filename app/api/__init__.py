from __future__ import annotations

import importlib
import pkgutil
from typing import Iterator

from fastapi import APIRouter


def iter_routers() -> Iterator[APIRouter]:
    for module_info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        if module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        router = getattr(module, "router", None)
        if isinstance(router, APIRouter):
            yield router


__all__ = ["iter_routers"]
