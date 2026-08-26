"""SoAI - Subprocess termination primitives [backend/core/process/termination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import signal

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC, RESPONSIVE_TIMEOUT_SEC

__all__ = ("terminate_subprocess_gracefully",)


def _signal_process(
    process: asyncio.subprocess.Process,
    *,
    process_group: bool,
    force: bool,
) -> bool:
    try:
        if process_group:
            os.killpg(
                process.pid,
                signal.SIGKILL if force else signal.SIGTERM,
            )
        elif force:
            process.kill()
        else:
            process.terminate()
    except ProcessLookupError:
        return False
    return True


async def terminate_subprocess_gracefully(
    process: asyncio.subprocess.Process,
    *,
    graceful_timeout_sec: float = float(RESPONSIVE_TIMEOUT_SEC),
    logger: LoggerProtocol,
    operation: str,
    process_group: bool = False,
) -> None:
    try:
        _signal_process(process, process_group=process_group, force=False)
        try:
            await asyncio.wait_for(process.wait(), timeout=graceful_timeout_sec)
        except TimeoutError:
            _signal_process(process, process_group=process_group, force=True)
            await asyncio.wait_for(process.wait(), timeout=LOCAL_IO_TIMEOUT_SEC)
    except RECOVERABLE_EXCEPTIONS as termination_error:
        log_exception(
            logger,
            termination_error,
            message="Error during subprocess termination",
            operation=operation,
            level="warning",
        )
        raise ProcessError(
            "Subprocess termination failed.",
            operation=operation,
            cause=termination_error,
        ) from termination_error
