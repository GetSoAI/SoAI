"""SoAI - Durable process shutdown marker lifecycle [backend/core/runtime/shutdown_marker.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.errors.exception_logging import log_exception
from core.files.operations import async_remove
from core.filesystem.async_queries import async_path_exists
from core.filesystem.atomic_writes import atomic_write_text_content
from core.logging.protocols import LoggerProtocol

__all__ = (
    "clear_process_shutdown_marker",
    "mark_process_started",
    "resolve_process_shutdown_marker_path",
)

OPERATION_CLEAR = "core.runtime.shutdown_marker.clear"
OPERATION_MARK_STARTED = "core.runtime.shutdown_marker.mark_started"


def resolve_process_shutdown_marker_path(system_data_path: str) -> str:
    return os.path.join(system_data_path, "soai_process.dirty")


async def mark_process_started(path: str, logger: LoggerProtocol) -> bool:
    unclean_shutdown_detected = await async_path_exists(path)
    if unclean_shutdown_detected:
        logger.warning(
            "SoAI did not shut down cleanly during its previous run. Checking database integrity before startup continues...",
        )
    try:
        await asyncio.to_thread(
            atomic_write_text_content,
            path,
            "",
            encoding="utf-8",
            errors="strict",
            ensure_parent=True,
            fsync=True,
            fsync_parent_directory=True,
        )
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to create the SoAI process shutdown marker.",
            operation=OPERATION_MARK_STARTED,
            level="warning",
        )
    return unclean_shutdown_detected


async def clear_process_shutdown_marker(path: str, logger: LoggerProtocol) -> None:
    try:
        if await async_path_exists(path):
            await async_remove(path)
    except OSError as exception:
        log_exception(
            logger,
            exception,
            message="Failed to clear the SoAI process shutdown marker.",
            operation=OPERATION_CLEAR,
            level="warning",
        )
