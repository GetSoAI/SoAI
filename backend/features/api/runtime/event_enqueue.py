"""SoAI - API runtime queue enqueue helpers [backend/features/api/runtime/event_enqueue.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.queue_backpressure import (
    BackpressureDeliveryStatus,
    put_with_backpressure,
)
from core.logging.trace import get_logger
from core.timing.constants import CONTROL_TIMEOUT_SEC
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker

__all__ = (
    "enqueue_correlated_media_event",
    "enqueue_event_must_deliver",
    "enqueue_event_or_warn",
)

LOGGER_NAME = "SoAI.features.api.event_enqueue"


def enqueue_event_or_warn[EventItem](
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[EventItem],
    event: EventItem,
    context_label: str,
) -> bool:
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        enqueue_warning_tracker.record_queue_full(context_label, logger=get_logger(LOGGER_NAME))
        return False
    return True


async def enqueue_correlated_media_event[EventItem](
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[EventItem],
    event: EventItem,
    shutdown_event: asyncio.Event,
    context_label: str,
) -> bool:
    if shutdown_event.is_set():
        return False
    delivery_result = await put_with_backpressure(queue, event, shutdown_event)
    if delivery_result.status in {
        BackpressureDeliveryStatus.DELIVERED,
        BackpressureDeliveryStatus.DELIVERED_AFTER_WAIT,
    }:
        return True
    shutdown_event.set()
    if delivery_result.status is BackpressureDeliveryStatus.TIMEOUT:
        enqueue_warning_tracker.record_queue_full(context_label, logger=get_logger(LOGGER_NAME))
    return False


async def enqueue_event_must_deliver[EventItem](
    queue: asyncio.Queue[EventItem],
    event: EventItem,
    context_label: str,
) -> bool:
    try:
        await asyncio.wait_for(queue.put(event), timeout=CONTROL_TIMEOUT_SEC)
    except TimeoutError:
        get_logger(LOGGER_NAME).warning(
            "Timed out applying backpressure for %s.",
            context_label,
        )
        return False
    return True
