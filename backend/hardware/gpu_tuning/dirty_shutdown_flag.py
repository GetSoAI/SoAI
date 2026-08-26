"""SoAI - GPU tuning dirty shutdown flag lifecycle [backend/hardware/gpu_tuning/dirty_shutdown_flag.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.files.operations import async_remove
from core.filesystem.async_queries import async_path_exists
from core.logging.protocols import TraceLogger

__all__ = ("clear_dirty_shutdown_flag_file",)

OPERATION = "hardware_presets.clear_dirty_shutdown_flag"


async def clear_dirty_shutdown_flag_file(path: str, logger: TraceLogger) -> None:
    if await async_path_exists(path):
        logger.trace("Clean shutdown detected. Removing GPU settings dirty flag.")
        try:
            await async_remove(path)
        except OSError as exception:
            log_exception(
                logger,
                exception,
                message="Failed to remove GPU settings dirty flag on shutdown",
                operation=OPERATION,
                level="warning",
            )
