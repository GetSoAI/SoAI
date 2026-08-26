"""SoAI - Timed stream iteration for persistence flushing [backend/features/api/routes/openai/responses/streaming_generator/timed_stream_iteration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.events.types_base import Event
from features.api.streaming.stream_iteration import StreamEvent, StreamTermination

__all__ = ("iter_openai_classified_items_with_flush_timer",)

NEXT_ITEM_TASK_NAME = (
    "features.api.routes.openai.responses.streaming_generator.timed_stream_iteration.next_item"
)


async def iter_openai_classified_items_with_flush_timer(
    stream: AsyncGenerator[bytes | StreamEvent[Event] | StreamTermination],
    *,
    should_flush: Callable[[], bool],
    flush_interval_ms: int,
    flush: Callable[[], Awaitable[None]],
) -> AsyncGenerator[bytes | StreamEvent[Event] | StreamTermination]:
    next_item_task: asyncio.Task[bytes | StreamEvent[Event] | StreamTermination] | None = None
    try:
        while True:
            if next_item_task is None:
                next_item_task = create_ephemeral_task(
                    anext(stream),
                    name=NEXT_ITEM_TASK_NAME,
                    log_exceptions=False,
                )
            if (
                should_flush()
                and next_item_task is not None
                and not next_item_task.done()
                and int(flush_interval_ms) > 0
            ):
                done, _pending = await asyncio.wait(
                    (next_item_task,),
                    timeout=float(flush_interval_ms) / 1000.0,
                )
                if not done:
                    await flush()
                    continue
            if next_item_task is None:
                break
            try:
                item = await next_item_task
            except StopAsyncIteration:
                break
            next_item_task = None
            yield item
    finally:
        try:
            if next_item_task is not None and not next_item_task.done():
                next_item_task.cancel()
                try:
                    await uncancel_then_cleanup(next_item_task)
                except asyncio.CancelledError:
                    next_item_task = None
        finally:
            await uncancel_then_cleanup(stream.aclose())
