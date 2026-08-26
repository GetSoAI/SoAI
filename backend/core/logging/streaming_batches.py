"""SoAI - Streaming log batch generator [backend/core/logging/streaming_batches.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import AsyncGenerator, Callable
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.deadlines import deadline_remaining
from core.concurrency.task_groups import QueueEventWaiter
from core.errors.exceptions import SoAITimeoutError, ValidationError
from core.logging.handlers.streaming import StreamingLogHandler

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("stream_log_batches",)


async def stream_log_batches(
    *,
    handler: StreamingLogHandler,
    source: str,
    batch_size: int,
    timeout: float,
    shutdown_event: asyncio.Event,
    idle_ping_interval: float,
    min_batch_interval: float,
    get_current_handler: Callable[[str], StreamingLogHandler | None],
) -> AsyncGenerator[JSONDict]:
    if batch_size <= 0:
        raise ValidationError("batch_size must be a positive integer.")
    queue: asyncio.Queue[JSONDict] = asyncio.Queue(maxsize=max(1, handler.capacity))
    heartbeat_interval = max(float(idle_ping_interval or 0.0), 0.0)
    batch_interval = max(float(min_batch_interval or 0.0), 0.0)
    last_activity = time.monotonic()
    handler.add_listener(queue)
    waiter = QueueEventWaiter(queue, shutdown_event)
    try:
        history = handler.get_recent(handler.capacity)
        if history:
            yield {"type": "batch", "mode": "history", "entries": history}
        while not shutdown_event.is_set():
            batch: deque[JSONDict] = deque(maxlen=batch_size)
            try:
                event = await waiter.wait(timeout=timeout)
                if event is None:
                    break
                batch.append({**event})
                if batch_interval > 0.0:
                    deadline = time.monotonic() + batch_interval
                    while len(batch) < batch_size:
                        remaining = deadline_remaining(deadline)
                        if remaining <= 0:
                            break
                        try:
                            next_event = await waiter.wait(timeout=remaining)
                        except (SoAITimeoutError, TimeoutError):
                            break
                        if next_event is None:
                            return
                        batch.append({**next_event})
                else:
                    while len(batch) < batch_size:
                        try:
                            batch.append({**queue.get_nowait()})
                        except asyncio.QueueEmpty:
                            break
                yield {"type": "batch", "mode": "live", "entries": list(batch)}
                last_activity = time.monotonic()
            except (SoAITimeoutError, TimeoutError):
                if get_current_handler(source) is not handler:
                    yield {"type": "reconfigured"}
                    break
                if heartbeat_interval:
                    now_ts = time.monotonic()
                    if now_ts - last_activity >= heartbeat_interval:
                        yield {"type": "heartbeat"}
                        last_activity = now_ts
                continue
    finally:
        await uncancel_then_cleanup(waiter.cancel())
        handler.remove_listener(queue)
