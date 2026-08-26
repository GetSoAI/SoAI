"""SoAI - Core async filesystem query utilities [backend/core/filesystem/async_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.filesystem.path_coercion import coerce_path

if TYPE_CHECKING:
    from core.filesystem.path_coercion import PathInput

__all__ = (
    "async_isdir",
    "async_isfile",
    "async_islink",
    "async_listdir",
    "async_makedirs",
    "async_path_exists",
)


async def async_path_exists(path: PathInput) -> bool:
    target = coerce_path(path)
    return await asyncio.to_thread(os.path.exists, target)


async def async_isdir(path: PathInput) -> bool:
    target = coerce_path(path)
    return await asyncio.to_thread(os.path.isdir, target)


async def async_isfile(path: PathInput) -> bool:
    target = coerce_path(path)
    return await asyncio.to_thread(os.path.isfile, target)


async def async_islink(path: PathInput) -> bool:
    target = coerce_path(path)
    return await asyncio.to_thread(os.path.islink, target)


async def async_makedirs(
    path: PathInput,
    exist_ok: bool = False,
    *,
    mode: int = 0o777,
) -> None:
    target = coerce_path(path)
    await asyncio.to_thread(os.makedirs, target, mode=mode, exist_ok=exist_ok)


async def async_listdir(path: PathInput) -> list[str]:
    target = coerce_path(path)
    return await asyncio.to_thread(os.listdir, target)
