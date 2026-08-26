"""SoAI - Terminal stream chunk drain ordering [backend/features/api/streaming/terminal_chunk_drain.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception
from core.events.types_base import Event
from core.events.types_models_streaming import StreamChunkEvent
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_event_streaming import (
    STREAMING_COUNTER_LISTENER_STALE_REMOVED,
)
from core.metrics.protocols import MetricsManagerProtocol
from core.timing.constants import MODERATE_DELAY_SEC
from features.api.streaming.delivery_metrics import record_delivery_metric
from features.api.streaming.stream_listener_cleanup import cleanup_stream_listener

__all__ = ("drain_terminal_chunk_queues",)

LOGGER_NAME = "SoAI.features.api.terminal_chunk_drain"
OPERATION = "api_streaming.broadcast_non_chunk"


async def drain_terminal_chunk_queues(
    *,
    lock: asyncio.Lock,
    listeners: dict[str, asyncio.Queue[Event | None]],
    pending_chunk_deliveries: dict[str, asyncio.Task[None]],
    pending_chunk_queues: dict[str, asyncio.Queue[StreamChunkEvent]],
    metrics_manager: MetricsManagerProtocol | None,
) -> set[str]:
    if not pending_chunk_queues:
        return set()
    logger = get_logger(LOGGER_NAME)
    timeout_listener_ids: set[str] = set()
    async with lock:
        chunk_queue_snapshot = list(pending_chunk_queues.items())
    drain_results = await asyncio.gather(
        *[
            asyncio.wait_for(
                chunk_queue.join(),
                timeout=MODERATE_DELAY_SEC,
            )
            for _, chunk_queue in chunk_queue_snapshot
        ],
        return_exceptions=True,
    )
    for (listener_id, _), drain_result in zip(chunk_queue_snapshot, drain_results, strict=False):
        if isinstance(drain_result, asyncio.TimeoutError):
            log_exception(
                logger,
                drain_result,
                message="Timeout draining chunk queue before terminal event delivery.",
                operation=OPERATION,
                level="warning",
            )
            timeout_listener_ids.add(listener_id)
            await cleanup_stream_listener(
                listener_id=listener_id,
                lock=lock,
                skip_current_task=False,
                listeners=listeners,
                pending_chunk_deliveries=pending_chunk_deliveries,
                pending_chunk_queues=pending_chunk_queues,
            )
        elif isinstance(drain_result, BaseException):
            log_exception(
                logger,
                drain_result,
                message="Unexpected chunk drain failure before terminal event delivery.",
                operation=OPERATION,
                level="warning",
            )
    if timeout_listener_ids:
        record_delivery_metric(
            metrics_manager,
            STREAMING_COUNTER_LISTENER_STALE_REMOVED,
            len(timeout_listener_ids),
        )
    return timeout_listener_ids
