"""SoAI - Process resource limit configuration [backend/core/system/resource_limits.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
import sys
import threading

import psutil

from core.errors.exceptions import ProcessError
from core.logging.configuration_constants import DEFAULT_LOG_DATE_FORMAT
from core.logging.formatters import UnifiedFormatter
from core.logging.trace import get_logger
from core.platform.os import is_linux, is_windows
from core.system.windows_process_memory_limit import limit_windows_process_memory
from core.timing.constants import TIGHT_POLL_INTERVAL_SEC
from core.timing.sleep import sleep_seconds

__all__ = (
    "PROCESS_MEMORY_SUPERVISION_EXIT_CODE",
    "configure_resource_limits",
    "limit_current_process_memory",
)

LOGGER_NAME = "SoAI.core.system.resource_limits"
ROOT_FILE_DESCRIPTOR_LIMIT = 1_048_576
PROCESS_MEMORY_SUPERVISION_EXIT_CODE = 4

if sys.platform != "win32":
    import resource

    RESOURCE = resource
else:
    RESOURCE = None


def configure_resource_limits() -> None:
    logger = get_logger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            UnifiedFormatter(
                "%(asctime)s - [SoAI/Bootstrap] - %(levelname)s - %(message)s",
                DEFAULT_LOG_DATE_FORMAT,
            ),
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    if is_windows():
        logger.debug("Adjusting the maximum number of open files is not supported on Windows.")
        return
    if RESOURCE is None:
        logger.debug("Adjusting the maximum number of open files is unavailable on this platform.")
        return
    soft, hard = RESOURCE.getrlimit(RESOURCE.RLIMIT_NOFILE)
    logger.debug("Current file descriptor limits: soft=%s, hard=%s (Unix).", soft, hard)
    if os.geteuid() == 0:
        try:
            RESOURCE.setrlimit(
                RESOURCE.RLIMIT_NOFILE,
                (ROOT_FILE_DESCRIPTOR_LIMIT, ROOT_FILE_DESCRIPTOR_LIMIT),
            )
            new_soft, new_hard = RESOURCE.getrlimit(RESOURCE.RLIMIT_NOFILE)
            logger.debug(
                "Running as root. Set file descriptor limits to: soft=%s, hard=%s.",
                new_soft,
                new_hard,
            )
        except (ValueError, PermissionError) as exception:
            logger.warning("Failed to raise file descriptor limits. Reason: %s", str(exception))
    else:
        logger.debug("Not running as root. Will not attempt to raise file descriptor limits.")


def limit_current_process_memory(max_bytes: int, *, exceeded_exit_code: int) -> None:
    if not is_linux() or RESOURCE is None:
        if is_windows():
            limit_windows_process_memory(max_bytes)
        _start_resident_memory_watchdog(max_bytes, exceeded_exit_code)
        return
    _soft, hard = RESOURCE.getrlimit(RESOURCE.RLIMIT_AS)
    limit = max_bytes if hard == RESOURCE.RLIM_INFINITY else min(max_bytes, hard)
    try:
        RESOURCE.setrlimit(RESOURCE.RLIMIT_AS, (limit, hard))
    except (ValueError, OSError) as exception:
        raise ProcessError("Process address space limit could not be applied.") from exception


def _start_resident_memory_watchdog(max_bytes: int, exceeded_exit_code: int) -> None:
    watchdog = threading.Thread(
        target=_watch_resident_memory,
        args=(psutil.Process(), max_bytes, exceeded_exit_code),
        name="soai-process-memory-watchdog",
        daemon=True,
    )
    try:
        watchdog.start()
    except (RuntimeError, OSError) as exception:
        raise ProcessError("Process memory watchdog could not start.") from exception


def _watch_resident_memory(
    process: psutil.Process, max_bytes: int, exceeded_exit_code: int
) -> None:
    try:
        while process.memory_info().rss <= max_bytes:
            sleep_seconds(TIGHT_POLL_INTERVAL_SEC)
    except (psutil.Error, OSError):
        os._exit(PROCESS_MEMORY_SUPERVISION_EXIT_CODE)
    os._exit(exceeded_exit_code)
