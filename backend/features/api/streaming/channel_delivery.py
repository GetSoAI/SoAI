"""SoAI - Task stream channel event delivery operations [backend/features/api/streaming/channel_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.queue_backpressure import (
    BackpressureDeliveryStatus,
    put_with_backpressure,
)
from core.errors.exception_logging import log_exception
from core.events.types_base import Event
from core.events.types_models_streaming import StreamChunkEvent
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_event_streaming import (
    STREAMING_COUNTER_DELIVERY_FAILED,
    STREAMING_COUNTER_DELIVERY_SHUTDOWN,
    STREAMING_COUNTER_DELIVERY_TIMEOUT,
    STREAMING_COUNTER_LISTENER_STALE_REMOVED,
    STREAMING_COUNTER_TERMINAL_DELIVERY_FAILED,
)
from core.metrics.protocols import MetricsManagerProtocol
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.timing.constants import OCR_TIMEOUT_SEC
from features.api.streaming.chunk_delivery_workers import (
    CHUNK_QUEUE_MAXSIZE,
    run_chunk_delivery_loop,
)
from features.api.streaming.delivery_metrics import record_delivery_metric
from features.api.streaming.stream_listener_cleanup import (
    cleanup_stream_listener,
    stop_chunk_delivery_workers,
)
from features.api.streaming.terminal_chunk_drain import drain_terminal_chunk_queues

__all__ = (
    "broadcast_non_chunk",
    "broadcast_stream_chunk",
    "deliver_non_chunk_to_listener",
)

LOGGER_NAME = "SoAI.features.api.channel_delivery"
OPERATION = "api_streaming.broadcast_non_chunk"


async def deliver_non_chunk_to_listener(
    listener_id: str,
    queue: asyncio.Queue[Event | None],
    event: Event | None,
    is_terminal: bool,
    shutdown_event: asyncio.Event,
    task_id: str | None,
    metrics_manager: MetricsManagerProtocol | None,
) -> str | None:
    logger = get_logger(LOGGER_NAME)
    delivery_result = await put_with_backpressure(
        queue,
        event,
        shutdown_event,
        backpressure_timeout=OCR_TIMEOUT_SEC,
    )
    if delivery_result.status in (
        BackpressureDeliveryStatus.DELIVERED,
        BackpressureDeliveryStatus.DELIVERED_AFTER_WAIT,
    ):
        return None
    if delivery_result.status == BackpressureDeliveryStatus.TIMEOUT:
        record_delivery_metric(metrics_manager, STREAMING_COUNTER_DELIVERY_TIMEOUT)
        if is_terminal:
            record_delivery_metric(metrics_manager, STREAMING_COUNTER_TERMINAL_DELIVERY_FAILED)
            logger.warning(
                "Failed to deliver terminal event to listener %s before timeout (task_id=%s)",
                listener_id,
                task_id,
            )
        else:
            record_delivery_metric(metrics_manager, STREAMING_COUNTER_DELIVERY_FAILED)
        return listener_id
    record_delivery_metric(metrics_manager, STREAMING_COUNTER_DELIVERY_SHUTDOWN)
    if is_terminal:
        logger.debug(
            "Terminal delivery aborted due to shutdown (listener=%s, task_id=%s)",
            listener_id,
            task_id,
        )
        return listener_id
    return None


async def broadcast_stream_chunk(
    listeners_snapshot: list[tuple[str, asyncio.Queue[Event | None]]],
    event: StreamChunkEvent,
    shutdown_event: asyncio.Event,
    task_id: str | None,
    metrics_manager: MetricsManagerProtocol | None,
    lock: asyncio.Lock,
    listeners: dict[str, asyncio.Queue[Event | None]],
    pending_chunk_deliveries: dict[str, asyncio.Task[None]],
    pending_chunk_queues: dict[str, asyncio.Queue[StreamChunkEvent]],
    *,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
) -> None:
    logger = get_logger(LOGGER_NAME)
    stale_listeners: list[str] = []
    for listener_id, _ in listeners_snapshot:
        chunk_queue = pending_chunk_queues.get(listener_id)
        pending_task = pending_chunk_deliveries.get(listener_id)
        if chunk_queue is None or pending_task is None or pending_task.done():
            async with lock:
                active_listener_queue = listeners.get(listener_id)
                if active_listener_queue is None:
                    continue
                chunk_queue = pending_chunk_queues.get(listener_id)
                pending_task = pending_chunk_deliveries.get(listener_id)
                if chunk_queue is None or pending_task is None or pending_task.done():
                    chunk_queue = asyncio.Queue[StreamChunkEvent](maxsize=CHUNK_QUEUE_MAXSIZE)
                    pending_chunk_queues[listener_id] = chunk_queue
                    pending_task = spawn_tracked_task(
                        run_chunk_delivery_loop(
                            listener_id,
                            active_listener_queue,
                            chunk_queue,
                            shutdown_event,
                            OCR_TIMEOUT_SEC,
                            task_id,
                            metrics_manager,
                            lock,
                            listeners,
                            pending_chunk_deliveries,
                            pending_chunk_queues,
                        ),
                        name=f"chunk-delivery-loop-{listener_id[:8]}",
                        logger=logger,
                        cancellation_binder=cancellation_binder,
                        finalizer_tracker=finalizer_tracker,
                        cancellation_id=build_soai_id(
                            (
                                "sys",
                                "streaming",
                                "chunk_delivery",
                                safe_or_hashed_segment(listener_id[:12]),
                            ),
                        ),
                        owner="chunk_delivery_loop",
                    )
                    pending_chunk_deliveries[listener_id] = pending_task
        if chunk_queue is None:
            continue
        try:
            chunk_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "Listener %s chunk queue saturated; evicting listener (task_id=%s)",
                listener_id,
                task_id,
            )
            stale_listeners.append(listener_id)
    if stale_listeners:
        record_delivery_metric(
            metrics_manager,
            STREAMING_COUNTER_LISTENER_STALE_REMOVED,
            len(stale_listeners),
        )
        for listener_id in stale_listeners:
            await cleanup_stream_listener(
                listener_id=listener_id,
                lock=lock,
                listeners=listeners,
                pending_chunk_deliveries=pending_chunk_deliveries,
                pending_chunk_queues=pending_chunk_queues,
                skip_current_task=False,
            )
            logger.warning(
                "Removed stale listener %s after chunk queue saturation (task_id=%s)",
                listener_id,
                task_id,
            )


async def broadcast_non_chunk(
    listeners_snapshot: list[tuple[str, asyncio.Queue[Event | None]]],
    event: Event | None,
    is_terminal: bool,
    shutdown_event: asyncio.Event,
    task_id: str | None,
    metrics_manager: MetricsManagerProtocol | None,
    lock: asyncio.Lock,
    listeners: dict[str, asyncio.Queue[Event | None]],
    pending_chunk_deliveries: dict[str, asyncio.Task[None]],
    pending_chunk_queues: dict[str, asyncio.Queue[StreamChunkEvent]],
) -> None:
    logger = get_logger(LOGGER_NAME)
    terminal_timeout_listener_ids: set[str] = set()
    if is_terminal:
        terminal_timeout_listener_ids = await drain_terminal_chunk_queues(
            lock=lock,
            listeners=listeners,
            pending_chunk_deliveries=pending_chunk_deliveries,
            pending_chunk_queues=pending_chunk_queues,
            metrics_manager=metrics_manager,
        )
    listeners_to_notify = [
        (listener_id, queue)
        for listener_id, queue in listeners_snapshot
        if listener_id not in terminal_timeout_listener_ids
    ]
    delivery_results = await asyncio.gather(
        *[
            deliver_non_chunk_to_listener(
                listener_id,
                queue,
                event,
                is_terminal,
                shutdown_event,
                task_id,
                metrics_manager,
            )
            for listener_id, queue in listeners_to_notify
        ],
        return_exceptions=True,
    )
    stale_listener_ids: set[str] = set()
    for result in delivery_results:
        if isinstance(result, str):
            stale_listener_ids.add(result)
        elif isinstance(result, BaseException):
            log_exception(
                logger,
                result,
                message="Unexpected exception during non-chunk broadcast delivery.",
                operation=OPERATION,
                level="warning",
            )
    if stale_listener_ids:
        record_delivery_metric(
            metrics_manager,
            STREAMING_COUNTER_LISTENER_STALE_REMOVED,
            len(stale_listener_ids),
        )
        for listener_id in stale_listener_ids:
            await cleanup_stream_listener(
                listener_id=listener_id,
                lock=lock,
                listeners=listeners,
                pending_chunk_deliveries=pending_chunk_deliveries,
                pending_chunk_queues=pending_chunk_queues,
                skip_current_task=False,
            )
    if is_terminal:
        await stop_chunk_delivery_workers(
            lock,
            pending_chunk_deliveries,
            pending_chunk_queues,
        )
