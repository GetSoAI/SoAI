"""SoAI - Task stream channel listener queue helpers [backend/features/api/streaming/task_stream_channel_listeners.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import deque

from core.events.types_base import Event
from core.runtime.soai_identifiers import create_prefixed_hex_id
from features.api.streaming.internal_protocols import TaskStreamChannelProtocol
from features.api.streaming.task_stream_subscription import StreamSubscription

__all__ = ("create_stream_subscription",)


async def create_stream_subscription(
    channel: TaskStreamChannelProtocol,
    *,
    lock: asyncio.Lock,
    buffer: deque[Event],
    listener_maxsize: int,
    listeners: dict[str, asyncio.Queue[Event | None]],
) -> StreamSubscription:
    listener_id = create_prefixed_hex_id("listener")
    async with lock:
        buffered = tuple(buffer)
        is_closed = channel.is_closed
        queue_size = max(listener_maxsize, len(buffered))
        if is_closed:
            queue_size = max(queue_size, len(buffered) + 1)
        queue: asyncio.Queue[Event | None] = asyncio.Queue(maxsize=queue_size)
        for event in buffered:
            queue.put_nowait(event)
        if is_closed:
            queue.put_nowait(None)
        else:
            listeners[listener_id] = queue
    return StreamSubscription(channel, listener_id, queue)
