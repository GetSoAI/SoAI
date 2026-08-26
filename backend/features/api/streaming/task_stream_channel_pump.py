"""SoAI - Task stream channel pump loop [backend/features/api/streaming/task_stream_channel_pump.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import QueueEventWaiter, cancel_and_await
from core.errors.exceptions import SoAITimeoutError
from core.events.types_models_streaming import StreamChunkEvent
from core.logging.trace import get_logger
from core.timing.constants import CONTROL_TIMEOUT_SEC
from features.api.streaming.chunk_batcher import (
    STREAM_CHUNK_BATCH_MAX_DELAY_SEC,
    StreamChunkBatcher,
)
from features.api.streaming.internal_protocols import TaskStreamChannelPumpProtocol
from features.api.streaming.task_stream_channel_cleanup import (
    signal_reply_queue_task_done_safe,
)
from features.api.streaming.task_stream_channel_terminal_retention import (
    resolve_retained_terminal_event,
)
from features.api.streaming.terminal_events import is_terminal_task_stream_event

__all__ = ("run_pump_loop",)

LOGGER_NAME = "SoAI.features.api.task_stream_channel_pump"


async def run_pump_loop(self: TaskStreamChannelPumpProtocol) -> None:
    logger = get_logger(LOGGER_NAME)
    waiter = QueueEventWaiter(self.reply_queue, self.shutdown_event)
    chunk_batcher = StreamChunkBatcher()
    try:
        while True:
            batch_timeout = (
                STREAM_CHUNK_BATCH_MAX_DELAY_SEC
                if chunk_batcher.has_pending()
                else CONTROL_TIMEOUT_SEC
            )
            try:
                wait_result = await waiter.wait_with_result(timeout=batch_timeout)
            except (SoAITimeoutError, TimeoutError):
                if self.terminal_retention.has_expired():
                    async with self.lock:
                        self.is_closed = True
                    break
                if chunk_batcher.should_flush():
                    await self.flush_chunk_batch(chunk_batcher)
                    continue
                terminal_event = await resolve_retained_terminal_event(
                    retention=self.terminal_retention,
                    task_registry=self.task_registry,
                    task_id=self.task_id,
                    metrics_manager=self.metrics_manager,
                    logger=logger,
                )
                if terminal_event is None:
                    continue
                async with self.lock:
                    listener_count = len(self.listeners)
                    self.buffer.append(terminal_event)
                await self.broadcast(terminal_event)
                logger.debug(
                    "Retained synthesized terminal event for %d listener(s) (task_id=%s)",
                    listener_count,
                    self.task_id,
                )
                if self.terminal_retention.has_expired():
                    async with self.lock:
                        self.is_closed = True
                    break
                continue
            event = wait_result.event
            if not wait_result.retrieved_from_queue:
                await self.flush_chunk_batch(chunk_batcher)
                async with self.lock:
                    self.is_closed = True
                break
            signal_reply_queue_task_done_safe(
                reply_queue=self.reply_queue,
                metrics_manager=self.metrics_manager,
                logger=logger,
            )
            if event is None:
                await self.flush_chunk_batch(chunk_batcher)
                async with self.lock:
                    self.is_closed = True
                break
            if isinstance(event, StreamChunkEvent):
                chunk_batcher.add(event.chunk)
                if chunk_batcher.should_flush():
                    await self.flush_chunk_batch(chunk_batcher)
                continue
            await self.flush_chunk_batch(chunk_batcher)
            async with self.lock:
                self.buffer.append(event)
            await self.broadcast(event)
            if is_terminal_task_stream_event(event):
                self.terminal_retention.mark_terminal_observed()
                if self.terminal_retention.has_expired():
                    async with self.lock:
                        self.is_closed = True
                    break
    finally:
        await uncancel_then_cleanup(waiter.cancel())
        await self.flush_chunk_batch(chunk_batcher)
        async with self.lock:
            self.is_closed = True
        await self.broadcast(None)
        if self.task_id and self.terminal_retention.completion_event is not None:
            if not self.terminal_retention.completion_event.is_set():
                await self.task_registry.release_completion_event(self.task_id)
        terminal_deadline = self.terminal_retention.terminal_deadline
        if terminal_deadline is not None:
            delay_seconds = terminal_deadline.remaining_seconds()
            if delay_seconds > 0.0:
                shutdown_wait_task = create_ephemeral_task(self.shutdown_event.wait())
                _, pending = await asyncio.wait({shutdown_wait_task}, timeout=delay_seconds)
                if pending:
                    shutdown_wait_task.cancel()
                    await cancel_and_await((shutdown_wait_task,), task_label="shutdown wait task")
                    if not shutdown_wait_task.cancelled():
                        exception = shutdown_wait_task.exception()
                        if exception is not None:
                            raise exception
        await self.registry.discard(self.reply_queue)
