"""SoAI - WebSocket log stream queue delivery and drop metrics [backend/features/api/routes/system/events/websocket_log_stream/delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.queue_backpressure import (
    BackpressureDeliveryStatus,
    put_with_backpressure,
)
from core.concurrency.queue_ops import (
    QueueDropTracker,
    log_queue_drop_with_tracker,
)
from core.metrics.keyspace_paths_event_streaming import (
    WEBSOCKET_COUNTER_LOG_STREAM_DROPS,
    WEBSOCKET_GAUGE_QUEUE_DEPTH,
)

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.types.json import JSONDict
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "enqueue_log_batch",
    "record_log_drop",
    "update_log_queue_metrics",
)


def update_log_queue_metrics(connection: WebsocketConnection, queue_depth: int) -> None:
    user_key_value = connection.user.get("username")
    user_key = (
        user_key_value if isinstance(user_key_value, str) and user_key_value.strip() else "unknown"
    )
    connection.api_context.dependencies.metrics_manager.set_gauge(
        *WEBSOCKET_GAUGE_QUEUE_DEPTH,
        user_key,
        value=queue_depth,
    )


def record_log_drop(
    logger: TraceLogger,
    connection: WebsocketConnection,
    entry_count: int,
    queue_depth: int,
    queue_max: int,
    drop_tracker: QueueDropTracker,
    *,
    dropped_count: int | None = None,
) -> None:
    if entry_count <= 0:
        return
    user_key_value = connection.user.get("username")
    user_key = (
        user_key_value if isinstance(user_key_value, str) and user_key_value.strip() else "unknown"
    )
    connection.api_context.dependencies.metrics_manager.increment_counter(
        *WEBSOCKET_COUNTER_LOG_STREAM_DROPS,
        user_key,
        value=max(1, entry_count),
    )
    update_log_queue_metrics(connection, queue_depth)
    normalized_dropped_count = 1 if dropped_count is None else max(1, dropped_count)
    log_queue_drop_with_tracker(
        logger,
        drop_tracker,
        normalized_dropped_count,
        (
            f"Log stream backpressure for user {user_key} "
            f"(queue={queue_depth}/{queue_max or 'unbounded'})"
        ),
    )


async def enqueue_log_batch(
    logger: TraceLogger,
    connection: WebsocketConnection,
    payload: JSONDict,
    entry_count: int,
    shutdown_event: asyncio.Event,
    drop_tracker: QueueDropTracker,
) -> bool:
    delivery = await put_with_backpressure(
        connection.queue,
        payload,
        shutdown_event,
        overwrite_attempts=1,
        backpressure_timeout=0.0,
    )
    if delivery.status in (
        BackpressureDeliveryStatus.DELIVERED,
        BackpressureDeliveryStatus.DELIVERED_AFTER_WAIT,
    ):
        update_log_queue_metrics(connection, connection.queue.qsize())
        return True
    if delivery.status == BackpressureDeliveryStatus.TIMEOUT:
        record_log_drop(
            logger,
            connection,
            entry_count,
            connection.queue.qsize(),
            connection.queue.maxsize,
            drop_tracker=drop_tracker,
            dropped_count=delivery.dropped_count,
        )
    return False
