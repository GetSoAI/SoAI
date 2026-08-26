"""SoAI - Async filesystem removals for plugins [backend/plugin_sdk/filesystem/removal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files import operations
from core.filesystem.path_coercion import coerce_path

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput

__all__ = ("async_remove",)

core_async_remove = operations.async_remove


async def async_remove(path: PathInput) -> None:
    target = coerce_path(path)
    await core_async_remove(target)
