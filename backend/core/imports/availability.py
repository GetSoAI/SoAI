"""SoAI - Module availability checks [backend/core/imports/availability.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from importlib.util import find_spec

from core.errors.exceptions import StateError

__all__ = (
    "module_available",
    "require_module",
)


def module_available(module_name: str) -> bool:
    if not module_name:
        raise StateError("Module name must not be empty.")
    parts = module_name.split(".")
    if any(not part.isidentifier() for part in parts):
        raise StateError(f"Invalid module name: {module_name!r}")
    try:
        return find_spec(module_name) is not None
    except ValueError:
        return False


def require_module(module_name: str, *, feature: str) -> None:
    if not module_available(module_name):
        raise StateError(f"{feature} requires {module_name} to be installed")
