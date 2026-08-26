"""SoAI - POSIX plugin process-group survivor termination [backend/plugin_sdk/contracts/process_group_termination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os
import signal

from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_exception
from core.timing.constants import SHORT_POLL_INTERVAL_SEC

__all__ = ("terminate_remaining_process_group",)


def _process_group_exists(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


async def terminate_remaining_process_group(
    process_group_id: int,
    *,
    logger: logging.Logger,
    plugin_label: str,
    operation: str,
    timeout_sec: float,
) -> bool:
    try:
        await asyncio.to_thread(os.killpg, process_group_id, signal.SIGKILL)
    except ProcessLookupError:
        return True
    except (OSError, ValueError) as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to kill remaining {plugin_label} process group",
            operation=operation,
        )
        return False
    deadline = deadline_after(timeout_sec)
    while not deadline.expired():
        if not await asyncio.to_thread(_process_group_exists, process_group_id):
            return True
        await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)
    logger.error(
        "%s process group %s still exists after forceful cleanup.",
        plugin_label,
        process_group_id,
    )
    return False
