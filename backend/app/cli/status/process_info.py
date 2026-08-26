"""SoAI - CLI status process inspection [backend/app/cli/status/process_info.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import psutil

from app.cli.status.types import ProcessInfo
from core.config.byte_sizes import MIB_BYTES
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.epoch import epoch_seconds_float

__all__ = ("get_process_info_quick",)

LOGGER_NAME = "SoAI.app.cli.process_info"
OPERATION = "app.cli.status.get_process_info_quick"


def get_process_info_quick(pid: int) -> ProcessInfo | None:
    try:
        process = psutil.Process(pid)
        with process.oneshot():
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent(interval=0.1)
            num_threads = process.num_threads()
            create_time = process.create_time()
            now_epoch = epoch_seconds_float()
        return ProcessInfo(
            rss_mb=memory_info.rss / MIB_BYTES,
            cpu_percent=float(cpu_percent),
            num_threads=int(num_threads),
            uptime_ms=max(0.0, now_epoch - float(create_time)) * 1000.0,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to get process info (non-critical).",
            operation=OPERATION,
            level="debug",
        )
        return None
