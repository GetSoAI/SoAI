"""SoAI - Core filesystem size calculation utilities [backend/core/filesystem/size_calculation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger

__all__ = ("get_path_size",)

LOGGER_NAME = "SoAI.core.filesystem.size_calculation"
OPERATION = "plugin_sdk.filesystem.size_calculation.get_path_size"


async def get_path_size(path: str) -> int | None:

    def _get_size_sync(target_path: str) -> int | None:
        size: int | None = None
        try:
            if os.path.isfile(target_path):
                size = os.path.getsize(target_path)
                return size
            if os.path.isdir(target_path):
                total_size = 0
                for dirpath, _, filenames in os.walk(target_path):
                    for filename in filenames:
                        file_path = os.path.join(dirpath, filename)
                        if not os.path.islink(file_path) and os.path.isfile(file_path):
                            total_size += os.path.getsize(file_path)
                size = total_size
                return size
            return None
        except OSError as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message=f"Error calculating size for {target_path}",
                operation=OPERATION,
            )
            size = None
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                get_logger(LOGGER_NAME),
                exception,
                message=f"Unexpected error calculating size for {target_path}",
                operation=OPERATION,
            )
            size = None
        return size

    return await asyncio.to_thread(_get_size_sync, path)
