"""SoAI - Task stream channel queue cleanup helpers [backend/features/api/streaming/task_stream_channel_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.queue_ops import drain_queue_to_list
from core.metrics.keyspace_paths_event_streaming import (
    STREAMING_COUNTER_QUEUE_DOUBLE_FINALIZATION,
)
from features.api.streaming.delivery_metrics import record_delivery_metric

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.logging.protocols import TraceLogger
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = (
    "drain_channel_reply_queue",
    "signal_reply_queue_task_done_safe",
)


def drain_channel_reply_queue(reply_queue: asyncio.Queue[Event]) -> int:
    return len(drain_queue_to_list(reply_queue))


def signal_reply_queue_task_done_safe(
    *,
    reply_queue: asyncio.Queue[Event],
    metrics_manager: MetricsManagerProtocol | None,
    logger: TraceLogger,
) -> None:
    try:
        reply_queue.task_done()
    except ValueError:
        record_delivery_metric(metrics_manager, STREAMING_COUNTER_QUEUE_DOUBLE_FINALIZATION)
        logger.trace("task_done called on empty queue (expected during cleanup)")
