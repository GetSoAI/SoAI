"""SoAI - Event bus queue drain and reply-channel error operations [backend/core/events/bus_queue_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.queue_ops import (
    QueueDropTracker,
    log_queue_drop_with_tracker,
    put_nowait_with_overwrite,
)
from core.errors.error_types import ErrorType
from core.events.bus_sentinel import EventBusSentinel
from core.events.bus_worker import is_event_queue_item
from core.events.protocols import EventCompletionSignal
from core.events.types_base import ReplyableCommand
from core.events.types_plugins import ErrorEvent
from core.logging.protocols import TraceLogger

if TYPE_CHECKING:
    from core.events.bus_worker import EventQueueItem

__all__ = (
    "drain_queue_orphaned_completion_events",
    "send_error_to_reply_channel",
)


def drain_queue_orphaned_completion_events(
    queue: asyncio.Queue[EventQueueItem | type[EventBusSentinel]],
    sentinel: type[EventBusSentinel],
) -> list[EventCompletionSignal]:
    orphaned_completion_events: list[EventCompletionSignal] = []
    while True:
        try:
            item = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        queue.task_done()
        if item is sentinel or item is None:
            continue
        try:
            if is_event_queue_item(item):
                _, _, completion_event = item
                if completion_event is not None:
                    orphaned_completion_events.append(completion_event)
        except (TypeError, ValueError):
            continue
    return orphaned_completion_events


def send_error_to_reply_channel(
    event: ReplyableCommand,
    *,
    message: str,
    logger: TraceLogger,
    drop_tracker: QueueDropTracker,
) -> str:
    reply_channel = event.reply_channel
    error_event = ErrorEvent(
        message=message,
        error_type=ErrorType.SERVER_ERROR,
    )
    result = put_nowait_with_overwrite(reply_channel, error_event, overwrite_attempts=1)
    if result.delivered:
        return "sent"
    log_queue_drop_with_tracker(
        logger,
        drop_tracker,
        max(1, result.dropped_count),
        f"Reply channel full after overwrite attempt. Error event dropped for {type(event).__name__}.",
    )
    return "queue_full"
