"""SoAI - Queue backpressure delivery helpers [backend/core/concurrency/queue_backpressure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum, auto

from core.concurrency.queue_ops import put_nowait_with_overwrite
from core.concurrency.queue_race import (
    QueueRaceOutcome,
    race_queue_operation_against_signals,
)

__all__ = (
    "BackpressureDeliveryResult",
    "BackpressureDeliveryStatus",
    "put_with_backpressure",
)


class BackpressureDeliveryStatus(Enum):
    DELIVERED = auto()
    DELIVERED_AFTER_WAIT = auto()
    TIMEOUT = auto()
    SHUTDOWN = auto()


@dataclass(frozen=True, slots=True)
class BackpressureDeliveryResult[T]:
    status: BackpressureDeliveryStatus
    dropped_count: int


async def put_with_backpressure[T](
    queue: asyncio.Queue[T],
    event: T,
    shutdown_event: asyncio.Event,
    *,
    backpressure_timeout: float = 10.0,
    overwrite_attempts: int = 0,
) -> BackpressureDeliveryResult[T]:
    if queue is None:
        return BackpressureDeliveryResult(
            status=BackpressureDeliveryStatus.SHUTDOWN,
            dropped_count=0,
        )
    dropped_count = 0
    attempts = max(0, int(overwrite_attempts))
    if attempts > 0:
        overwrite_result = put_nowait_with_overwrite(queue, event, overwrite_attempts=attempts)
        dropped_count += overwrite_result.dropped_count
        if overwrite_result.delivered:
            return BackpressureDeliveryResult(
                status=BackpressureDeliveryStatus.DELIVERED,
                dropped_count=dropped_count,
            )
    try:
        queue.put_nowait(event)
        return BackpressureDeliveryResult(
            status=BackpressureDeliveryStatus.DELIVERED,
            dropped_count=dropped_count,
        )
    except asyncio.QueueFull:
        if shutdown_event.is_set():
            return BackpressureDeliveryResult(
                status=BackpressureDeliveryStatus.SHUTDOWN,
                dropped_count=dropped_count,
            )
    result = await race_queue_operation_against_signals(
        queue.put(event),
        (shutdown_event,),
        timeout_seconds=backpressure_timeout,
    )
    if result.outcome == QueueRaceOutcome.OPERATION_COMPLETED:
        return BackpressureDeliveryResult(
            status=BackpressureDeliveryStatus.DELIVERED_AFTER_WAIT,
            dropped_count=dropped_count,
        )
    if result.outcome == QueueRaceOutcome.SIGNAL_FIRED:
        return BackpressureDeliveryResult(
            status=BackpressureDeliveryStatus.SHUTDOWN,
            dropped_count=dropped_count,
        )
    return BackpressureDeliveryResult(
        status=BackpressureDeliveryStatus.TIMEOUT,
        dropped_count=dropped_count,
    )
