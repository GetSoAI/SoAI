"""SoAI - Anthropic stream heartbeat iteration [backend/features/api/routes/anthropic/stream_heartbeat.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from core.concurrency.async_iterators import close_async_iterator_after_read
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.tasks.protocols import TaskFinalizerTrackerProtocol

__all__ = ("iter_anthropic_chunks_with_heartbeats",)

_HEARTBEAT_INTERVAL_SECONDS = 15.0
_NEXT_CHUNK_TASK_NAME = "features.api.routes.anthropic.stream_heartbeat.next_chunk"


async def iter_anthropic_chunks_with_heartbeats(
    upstream: AsyncGenerator[bytes],
    *,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
) -> AsyncGenerator[bytes | None]:
    next_chunk_task: asyncio.Task[bytes] | None = None
    try:
        while True:
            if next_chunk_task is None:
                next_chunk_task = create_ephemeral_task(
                    anext(upstream),
                    name=_NEXT_CHUNK_TASK_NAME,
                    log_exceptions=False,
                )
            done, _pending = await asyncio.wait(
                (next_chunk_task,), timeout=_HEARTBEAT_INTERVAL_SECONDS
            )
            if not done:
                yield None
                continue
            try:
                chunk = next_chunk_task.result()
            except StopAsyncIteration:
                break
            finally:
                next_chunk_task = None
            yield chunk
    finally:
        await close_async_iterator_after_read(
            upstream, next_chunk_task, finalizer_tracker=finalizer_tracker
        )
