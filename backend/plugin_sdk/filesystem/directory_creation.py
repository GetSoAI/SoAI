"""SoAI - Directory creation operations for plugins [backend/plugin_sdk/filesystem/directory_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.files import operations
from core.filesystem.path_coercion import coerce_path

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput

__all__ = (
    "ensure_dirs_exist",
    "ensure_parent_dirs_exist",
)

core_ensure_dirs_exist = operations.ensure_dirs_exist
core_ensure_parent_dirs_exist = operations.ensure_parent_dirs_exist


async def ensure_dirs_exist(paths: Sequence[PathInput]) -> None:
    coerced_paths = [coerce_path(raw) for raw in paths]
    await core_ensure_dirs_exist(coerced_paths)


async def ensure_parent_dirs_exist(file_paths: Sequence[PathInput]) -> None:
    coerced_paths = [coerce_path(raw) for raw in file_paths]
    await core_ensure_parent_dirs_exist(coerced_paths)
