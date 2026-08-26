"""SoAI - File operation utilities [backend/core/files/operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from collections.abc import Sequence

from core.errors.exception_logging import log_handled_exception
from core.files.windows_reserved_names import WINDOWS_RESERVED_DEVICE_NAMES
from core.logging.protocols import LoggerProtocol

__all__ = (
    "async_remove",
    "async_remove_if_exists",
    "ensure_dirs_exist",
    "ensure_parent_dirs_exist",
    "remove_if_exists",
    "secure_filename",
)

_FILENAME_ASCII_STRIP_PATTERN = "[^A-Za-z0-9_.-]"
OPERATION_ASYNC_REMOVE_IF_EXISTS = "core.files.operations.async_remove_if_exists"


def secure_filename(filename: str) -> str:
    if not filename:
        return ""
    filename = os.path.basename(filename.replace("\\", "/"))
    filename = str(re.sub(_FILENAME_ASCII_STRIP_PATTERN, "_", filename)).strip("._")
    if filename.split(".", maxsplit=1)[0].upper() in WINDOWS_RESERVED_DEVICE_NAMES:
        filename = f"_{filename}"
    if not filename:
        filename = f"file_{uuid.uuid4().hex[:12]}"
    return filename[:240] if len(filename) > 240 else filename


async def async_remove(path: str) -> None:
    await asyncio.to_thread(os.remove, path)


def remove_if_exists(path: str) -> bool:
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False


async def async_remove_if_exists(
    path: str,
    *,
    logger: LoggerProtocol | None = None,
    log_level: int = logging.WARNING,
) -> bool:
    try:
        await async_remove(path)
        return True
    except FileNotFoundError:
        return False
    except OSError as exception:
        if logger:
            log_handled_exception(
                logger,
                exception,
                message="Failed to remove file.",
                operation=OPERATION_ASYNC_REMOVE_IF_EXISTS,
                details={"path": path},
                level=_log_level_name(log_level),
            )
        return False


def _log_level_name(log_level: int) -> str:
    level_name = logging.getLevelName(log_level)
    if isinstance(level_name, str):
        lowered = level_name.lower()
        if lowered in {"debug", "info", "warning", "error", "critical"}:
            return lowered
    return "warning"


async def ensure_dirs_exist(paths: Sequence[str]) -> None:
    if not paths:
        return
    directories: set[str] = set()
    for candidate in paths:
        if not candidate:
            continue
        normalized = os.path.normpath(candidate)
        if not normalized:
            continue
        trimmed = normalized.rstrip("/\\")
        if trimmed:
            directories.add(trimmed)
    if directories:
        mkdir_tasks = [
            asyncio.to_thread(os.makedirs, directory, exist_ok=True) for directory in directories
        ]
        await asyncio.gather(*mkdir_tasks, return_exceptions=False)


async def ensure_parent_dirs_exist(file_paths: Sequence[str]) -> None:
    if not file_paths:
        return
    parent_directories: set[str] = set()
    for candidate in file_paths:
        if not candidate:
            continue
        normalized = os.path.normpath(candidate)
        if not normalized:
            continue
        parent = os.path.dirname(normalized)
        if parent:
            parent_directories.add(parent)
    if parent_directories:
        mkdir_tasks = [
            asyncio.to_thread(os.makedirs, directory, exist_ok=True)
            for directory in parent_directories
        ]
        await asyncio.gather(*mkdir_tasks, return_exceptions=False)
