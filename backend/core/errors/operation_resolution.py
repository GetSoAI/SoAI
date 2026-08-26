"""SoAI - Error operation name resolution helpers [backend/core/errors/operation_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import inspect
from types import FrameType

__all__ = ("resolve_default_operation",)


def resolve_default_operation(*, frame_depth: int = 2) -> str | None:
    current_module = __name__
    frame: FrameType | None = inspect.currentframe()
    for _ in range(max(0, int(frame_depth))):
        frame = frame.f_back if frame is not None else None
    while frame is not None:
        module = frame.f_globals.get("__name__")
        if module in (current_module, "error_handler"):
            frame = frame.f_back
            continue
        module_name = module.rsplit(".", 1)[-1] if isinstance(module, str) else ""
        if module_name and module_name not in {"__init__"}:
            func = frame.f_code.co_name
            return module_name if func == "<module>" else f"{module_name}.{func}"
        frame = frame.f_back
    return None
