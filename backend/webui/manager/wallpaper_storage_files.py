"""SoAI - Wallpaper storage directory operations [backend/webui/manager/wallpaper_storage_files.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError
from core.files.operations import async_remove
from core.filesystem.async_queries import (
    async_isfile,
    async_listdir,
    async_makedirs,
    async_path_exists,
)
from core.logging.protocols import LoggerProtocol

__all__ = (
    "clear_wallpaper_dir",
    "collect_wallpaper_files",
    "ensure_wallpaper_storage_path",
    "prune_wallpaper_dir",
    "remove_wallpaper_file",
    "resolve_latest_wallpaper_file",
)

OPERATION_WEBUI_MANAGER_WALLPAPER_STORAGE_FILES_REMOVE_WALLPAPER_FILE = (
    "webui.manager.wallpaper_storage_files.remove_wallpaper_file"
)


async def ensure_wallpaper_storage_path(storage_path: str) -> str:
    if not await async_path_exists(storage_path):
        await async_makedirs(storage_path, exist_ok=True)
    return storage_path


async def collect_wallpaper_files(storage_path: str) -> list[tuple[str, os.stat_result]]:
    matches: list[tuple[str, os.stat_result]] = []
    try:
        for filename in await async_listdir(storage_path):
            if not filename.startswith("wallpaper."):
                continue
            file_path = os.path.join(storage_path, filename)
            if not await async_isfile(file_path):
                continue
            try:
                stat_result = await asyncio.to_thread(os.stat, file_path)
            except FileNotFoundError:
                continue
            matches.append((file_path, stat_result))
    except FileNotFoundError:
        return []
    return matches


async def remove_wallpaper_file(
    *,
    file_path: str,
    logger: LoggerProtocol,
    operation: str,
    raise_on_error: bool,
) -> bool:
    try:
        await async_remove(file_path)
        return True
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to delete old wallpaper file",
            operation=OPERATION_WEBUI_MANAGER_WALLPAPER_STORAGE_FILES_REMOVE_WALLPAPER_FILE,
            details={"file_path": file_path, "operation": operation},
            level="warning",
        )
        if raise_on_error:
            raise ProcessError(
                f"Could not remove existing wallpaper file: {exception}",
            ) from exception
        return False


async def clear_wallpaper_dir(*, storage_path: str, logger: LoggerProtocol) -> None:
    for file_path, _ in await collect_wallpaper_files(storage_path):
        await remove_wallpaper_file(
            file_path=file_path,
            logger=logger,
            operation="webui_manager.clear_existing_wallpapers",
            raise_on_error=True,
        )


async def prune_wallpaper_dir(
    *,
    storage_path: str,
    keep_file_path: str,
    logger: LoggerProtocol,
) -> None:
    for file_path, _ in await collect_wallpaper_files(storage_path):
        if file_path == keep_file_path:
            continue
        await remove_wallpaper_file(
            file_path=file_path,
            logger=logger,
            operation="webui_manager.prune_existing_wallpapers",
            raise_on_error=False,
        )


async def resolve_latest_wallpaper_file(
    storage_path: str,
) -> tuple[str | None, os.stat_result | None]:
    wallpaper_files = await collect_wallpaper_files(storage_path)
    if not wallpaper_files:
        return (None, None)
    selected_path, selected_stat = max(
        wallpaper_files,
        key=lambda item: (item[1].st_mtime, item[0]),
    )
    return (selected_path, selected_stat)
