"""SoAI - Media proxy cache pruning operations [backend/webui/manager/media_preview_proxy_cache_pruning.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger

__all__ = ("prune_cache_dir",)

LOGGER_NAME = "SoAI.webui.manager.media_preview_proxy_cache_pruning"
OPERATION_PRUNE = "webui.media.proxy.cache.prune"


@dataclass(frozen=True, slots=True)
class CacheDataEntry:
    data_path: str
    meta_path: str
    size_bytes: int
    mtime: float


async def prune_cache_dir(cache_dir: str, *, max_bytes: int) -> None:
    logger = get_logger(LOGGER_NAME)
    if max_bytes <= 0:
        return
    try:
        entries = await asyncio.to_thread(_list_cache_data_entries, cache_dir)
    except FileNotFoundError:
        return
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to list media proxy cache directory",
            operation=OPERATION_PRUNE,
            level="warning",
        )
        return
    total = sum(entry.size_bytes for entry in entries)
    if total <= max_bytes:
        return
    sorted_entries = sorted(entries, key=lambda entry: float(entry.mtime))
    for entry in sorted_entries:
        if total <= max_bytes:
            break
        removed = await _remove_cache_paths(data_path=entry.data_path, meta_path=entry.meta_path)
        if removed:
            total -= int(entry.size_bytes)


def _list_cache_data_entries(cache_dir: str) -> list[CacheDataEntry]:
    if not cache_dir:
        raise ValidationError("Cache directory must be provided.")
    entries: list[CacheDataEntry] = []
    for name in os.listdir(cache_dir):
        if not name.endswith(".bin"):
            continue
        base = name[: -len(".bin")]
        data_path = os.path.join(cache_dir, name)
        meta_path = os.path.join(cache_dir, f"{base}.json")
        stat_result = os.stat(data_path)
        entries.append(
            CacheDataEntry(
                data_path=data_path,
                meta_path=meta_path,
                size_bytes=int(stat_result.st_size),
                mtime=float(stat_result.st_mtime),
            ),
        )
    return entries


async def _remove_cache_paths(*, data_path: str, meta_path: str) -> bool:
    logger = get_logger(LOGGER_NAME)
    removed = False
    try:
        await asyncio.to_thread(os.remove, data_path)
        removed = True
    except FileNotFoundError:
        removed = False
    except OSError:
        removed = False
    try:
        await asyncio.to_thread(os.remove, meta_path)
    except FileNotFoundError:
        return removed
    except OSError as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to remove media proxy cache metadata file (non-critical).",
            operation=OPERATION_PRUNE,
            details={"path": meta_path},
            level="debug",
        )
    return removed
