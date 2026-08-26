"""SoAI - Deterministic cancel-watcher cleanup for async tasks [backend/core/tasks/cancel_watcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("cleanup_cancel_watcher",)

OPERATION_CORE_TASKS_CANCEL_WATCHER_CLEANUP_CANCEL_WATCHER = (
    "core.tasks.cancel_watcher.cleanup_cancel_watcher"
)


async def cleanup_cancel_watcher(
    cancel_watcher: asyncio.Task[None] | None,
    *,
    operation: str,
    logger: LoggerProtocol,
    details: Mapping[str, JSONValue] | None = None,
    error_level: str = "debug",
) -> None:
    if cancel_watcher is None:
        return
    cancel_watcher.cancel()
    try:
        await cancel_watcher
    except asyncio.CancelledError:
        logger.debug("Cancel watcher task finished after cancellation (expected).")
    except RECOVERABLE_EXCEPTIONS as exception:
        merged_details = dict(details or {})
        merged_details["cleanup_operation"] = operation
        log_handled_exception(
            logger,
            exception,
            message="Cancel watcher suppressed during cleanup (non-critical).",
            operation=OPERATION_CORE_TASKS_CANCEL_WATCHER_CLEANUP_CANCEL_WATCHER,
            details=merged_details,
            level=error_level,
        )
