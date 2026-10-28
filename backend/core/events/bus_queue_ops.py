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
from core.events.completion_signals import mark_completion_signal_not_enqueued
from core.events.types_base import ReplyableCommand
from core.events.types_plugins import ErrorEvent
from core.logging.protocols import TraceLogger

if TYPE_CHECKING:
    from core.events.bus_worker import EventQueueItem

__all__ = (
    "send_error_to_reply_channel",
    "settle_queued_events",
)


def settle_queued_events(
    queue: asyncio.Queue[EventQueueItem | type[EventBusSentinel]],
    *,
    failure_message: str,
    logger: TraceLogger,
    drop_tracker: QueueDropTracker,
) -> int:
    settled_count = 0
    while True:
        try:
            item = queue.get_nowait()
        except (asyncio.QueueEmpty, asyncio.QueueShutDown):
            return settled_count
        queue.task_done()
        if not is_event_queue_item(item):
            continue
        event, _publish_time, completion_signal = item
        mark_completion_signal_not_enqueued(completion_signal, failure_message=failure_message)
        if isinstance(event, ReplyableCommand):
            send_error_to_reply_channel(
                event,
                message=failure_message,
                logger=logger,
                drop_tracker=drop_tracker,
            )
        settled_count += 1


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
