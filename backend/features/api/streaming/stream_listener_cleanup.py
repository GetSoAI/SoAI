"""SoAI - Streaming listener cleanup ownership [backend/features/api/streaming/stream_listener_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.queue_ops import drain_queue_to_list, put_nowait_with_overwrite
from core.events.types_base import Event
from core.events.types_models_streaming import StreamChunkEvent

__all__ = (
    "cleanup_stream_listener",
    "stop_chunk_delivery_workers",
)


async def cleanup_stream_listener(
    *,
    listener_id: str,
    lock: asyncio.Lock,
    listeners: dict[str, asyncio.Queue[Event | None]],
    pending_chunk_deliveries: dict[str, asyncio.Task[None]],
    pending_chunk_queues: dict[str, asyncio.Queue[StreamChunkEvent]],
    skip_current_task: bool,
) -> None:
    current_task = asyncio.current_task() if skip_current_task else None
    async with lock:
        listener_queue = listeners.pop(listener_id, None)
        pending_task = pending_chunk_deliveries.pop(listener_id, None)
        chunk_queue = pending_chunk_queues.pop(listener_id, None)
    if pending_task is not None and pending_task is not current_task and not pending_task.done():
        pending_task.cancel()
    if chunk_queue is not None:
        drain_queue_to_list(chunk_queue)
    if listener_queue is not None:
        drain_queue_to_list(listener_queue)
        put_nowait_with_overwrite(listener_queue, None, overwrite_attempts=2)


async def stop_chunk_delivery_workers(
    lock: asyncio.Lock,
    pending_chunk_deliveries: dict[str, asyncio.Task[None]],
    pending_chunk_queues: dict[str, asyncio.Queue[StreamChunkEvent]],
) -> None:
    tasks_to_cancel: list[asyncio.Task[None]] = []
    async with lock:
        tasks_to_cancel = [task for task in pending_chunk_deliveries.values() if not task.done()]
        pending_chunk_deliveries.clear()
        pending_chunk_queues.clear()
    for task in tasks_to_cancel:
        task.cancel()
    if tasks_to_cancel:
        cleanup_results = await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        for cleanup_result in cleanup_results:
            if isinstance(cleanup_result, asyncio.CancelledError):
                continue
            if isinstance(cleanup_result, BaseException):
                raise cleanup_result
