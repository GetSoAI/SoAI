"""SoAI - Metrics queue operations handler [backend/metrics/manager/operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.queue_ops import (
    QueueDropReport,
    QueueDropTracker,
    log_queue_drop_with_tracker,
    put_nowait_with_overwrite,
)
from core.logging.trace import get_logger
from metrics.manager.types import MetricsWorkerPayload

if TYPE_CHECKING:
    from metrics.manager.types import (
        MetricsWorkerArgs,
        MetricsWorkerOptionValue,
        MetricsWorkerQueueItem,
    )

__all__ = (
    "MetricsQueueFullThrottle",
    "queue_metrics_operation",
)

LOGGER_NAME = "SoAI.metrics.manager.operations"


_QUEUE_FULL_WARNING_INTERVAL_SECONDS: float = 30.0


class MetricsQueueFullThrottle:
    __slots__ = ("_drop_tracker",)

    def __init__(self) -> None:
        self._drop_tracker = QueueDropTracker(_QUEUE_FULL_WARNING_INTERVAL_SECONDS)

    @property
    def total_dropped(self) -> int:
        return self._drop_tracker.total_dropped

    @property
    def drop_tracker(self) -> QueueDropTracker:
        return self._drop_tracker

    def record_drop(self) -> QueueDropReport:
        return self._drop_tracker.record_drop()


def queue_metrics_operation(
    background_queue: asyncio.Queue[MetricsWorkerQueueItem] | None,
    accepting_operations: bool,
    operation: str,
    args: MetricsWorkerArgs,
    option_values: dict[str, MetricsWorkerOptionValue],
    throttle: MetricsQueueFullThrottle,
) -> None:
    if background_queue is None or not accepting_operations:
        return
    payload: MetricsWorkerPayload = {"args": args, "options": dict(option_values)}
    delivery_result = put_nowait_with_overwrite(
        background_queue,
        (operation, payload),
        overwrite_attempts=0,
    )
    if delivery_result.delivered:
        return
    drop_report = throttle.record_drop()
    logger = get_logger(LOGGER_NAME)
    log_queue_drop_with_tracker(
        logger,
        throttle.drop_tracker,
        max(1, delivery_result.dropped_count),
        f"Metrics background queue full while scheduling operation '{operation}'.",
        drop_report=drop_report,
    )
