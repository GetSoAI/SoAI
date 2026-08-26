"""SoAI - Task stream chunk delivery worker lifecycle [backend/features/api/streaming/chunk_delivery_workers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.queue_backpressure import (
    BackpressureDeliveryStatus,
    put_with_backpressure,
)
from core.concurrency.queue_ops import (
    QueueDropTracker,
    log_queue_drop_with_tracker,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_models_streaming import StreamChunkEvent
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_event_streaming import (
    STREAMING_COUNTER_DELIVERY_SHUTDOWN,
    STREAMING_COUNTER_DELIVERY_TIMEOUT,
)
from core.metrics.protocols import MetricsManagerProtocol
from features.api.streaming.delivery_metrics import record_delivery_metric
from features.api.streaming.stream_listener_cleanup import cleanup_stream_listener

__all__ = (
    "CHUNK_QUEUE_MAXSIZE",
    "run_chunk_delivery_loop",
)

LOGGER_NAME = "SoAI.features.api.chunk_delivery_workers"
OPERATION = "api_streaming.run_chunk_delivery_loop"


CHUNK_QUEUE_MAXSIZE: int = 8
_CHUNK_STREAM_DROP_WARNING_INTERVAL_SECONDS: float = 30.0


async def run_chunk_delivery_loop(
    listener_id: str,
    queue: asyncio.Queue[Event | None],
    chunk_queue: asyncio.Queue[StreamChunkEvent],
    shutdown_event: asyncio.Event,
    backpressure_timeout: float,
    task_id: str | None,
    metrics_manager: MetricsManagerProtocol | None,
    lock: asyncio.Lock,
    listeners: dict[str, asyncio.Queue[Event | None]],
    pending_chunk_deliveries: dict[str, asyncio.Task[None]],
    pending_chunk_queues: dict[str, asyncio.Queue[StreamChunkEvent]],
) -> None:
    logger = get_logger(LOGGER_NAME)
    drop_tracker = QueueDropTracker(_CHUNK_STREAM_DROP_WARNING_INTERVAL_SECONDS)
    try:
        while True:
            event = await chunk_queue.get()
            try:
                delivery_result = await put_with_backpressure(
                    queue,
                    event,
                    shutdown_event,
                    backpressure_timeout=float(backpressure_timeout),
                )
            finally:
                chunk_queue.task_done()
            if delivery_result.status in (
                BackpressureDeliveryStatus.DELIVERED,
                BackpressureDeliveryStatus.DELIVERED_AFTER_WAIT,
            ):
                if delivery_result.status == BackpressureDeliveryStatus.DELIVERED_AFTER_WAIT:
                    logger.debug(
                        "Stream chunk delivered after backpressure wait (listener=%s, task_id=%s)",
                        listener_id,
                        task_id,
                    )
                continue
            if delivery_result.status == BackpressureDeliveryStatus.TIMEOUT:
                log_queue_drop_with_tracker(
                    logger,
                    drop_tracker,
                    max(1, delivery_result.dropped_count),
                    f"Stream chunk delivery for listener {listener_id} (task_id={task_id})",
                )
                record_delivery_metric(metrics_manager, STREAMING_COUNTER_DELIVERY_TIMEOUT)
                logger.warning(
                    "Stream chunk delivery timed out (listener=%s, task_id=%s, timeout=%.1fs). Evicting listener.",
                    listener_id,
                    task_id,
                    float(backpressure_timeout),
                )
            elif delivery_result.status == BackpressureDeliveryStatus.SHUTDOWN:
                record_delivery_metric(metrics_manager, STREAMING_COUNTER_DELIVERY_SHUTDOWN)
                logger.debug(
                    "Stream chunk delivery aborted due to shutdown (listener=%s, task_id=%s)",
                    listener_id,
                    task_id,
                )
            await cleanup_stream_listener(
                listener_id=listener_id,
                lock=lock,
                listeners=listeners,
                pending_chunk_deliveries=pending_chunk_deliveries,
                pending_chunk_queues=pending_chunk_queues,
                skip_current_task=True,
            )
            return
    except asyncio.CancelledError:
        return
    except RECOVERABLE_EXCEPTIONS as delivery_exception:
        coerced_error = coerce_to_soai_error(
            delivery_exception,
            operation="api_streaming.run_chunk_delivery_loop",
        )
        log_handled_exception(
            logger,
            coerced_error,
            message="Exception during chunk delivery loop (non-critical).",
            operation=OPERATION,
            level="warning",
        )
        await cleanup_stream_listener(
            listener_id=listener_id,
            lock=lock,
            listeners=listeners,
            pending_chunk_deliveries=pending_chunk_deliveries,
            pending_chunk_queues=pending_chunk_queues,
            skip_current_task=True,
        )
        return
    finally:
        current_task = asyncio.current_task()
        async with lock:
            running_task = pending_chunk_deliveries.get(listener_id)
            if running_task is current_task:
                pending_chunk_deliveries.pop(listener_id, None)
            pending_chunk_queues.pop(listener_id, None)
