"""SoAI - Backup task non-critical async operation execution [backend/app/backup/task_noncritical_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

__all__ = ("execute_noncritical_task_operation",)


async def execute_noncritical_task_operation[ResultT](
    *,
    operation_action: Awaitable[ResultT],
    log: LoggerProtocol,
    operation: str,
    message: str,
    task_id: str,
    level: str,
) -> ResultT | None:
    try:
        return await operation_action
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            log,
            exception,
            message=message,
            operation=operation,
            details={"task_id": str(task_id)},
            level=level,
        )
    return None
