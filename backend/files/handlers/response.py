"""SoAI - File handler reply channel helpers [backend/files/handlers/response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.queue_ops import put_nowait_with_overwrite
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.events.types_base import Event
from core.logging.protocols import StandardLogger

__all__ = (
    "deliver_reply_event_or_raise",
    "deliver_reply_event_with_warnings",
)


def _deliver_reply_event(
    reply_channel: asyncio.Queue[Event],
    event: Event,
    *,
    overwrite_attempts: int = 1,
) -> bool:
    return put_nowait_with_overwrite(
        reply_channel,
        event,
        overwrite_attempts=overwrite_attempts,
    ).delivered


def deliver_reply_event_or_raise(
    reply_channel: asyncio.Queue[Event],
    event: Event,
    logger: StandardLogger,
    *,
    operation: str,
    overwrite_attempts: int = 1,
) -> None:
    if _deliver_reply_event(
        reply_channel,
        event,
        overwrite_attempts=overwrite_attempts,
    ):
        return
    error = StateError(f"Reply channel unavailable while handling {operation}.")
    log_handled_exception(
        logger,
        error,
        message="Failed to deliver reply event.",
        operation=operation,
        level="error",
    )
    raise error


def deliver_reply_event_with_warnings(
    reply_channel: asyncio.Queue[Event],
    event: Event,
    logger: StandardLogger | None = None,
    *,
    operation: str,
    overwrite_attempts: int = 1,
) -> bool:
    if _deliver_reply_event(
        reply_channel,
        event,
        overwrite_attempts=overwrite_attempts,
    ):
        return True
    if logger is not None:
        error = StateError(f"Reply channel unavailable while handling {operation}.")
        log_handled_exception(
            logger,
            error,
            message="Could not enqueue warning-level reply event.",
            operation=operation,
        )
    return False
