"""SoAI - Task stream channel fanout and buffering [backend/features/api/streaming/task_stream_channel.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import deque

from core.events.types_base import Event
from core.events.types_models_streaming import StreamChunkEvent
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.runtime.soai_identifiers import build_soai_id, safe_or_hashed_segment
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from features.api.streaming.chunk_batcher import StreamChunkBatcher
from features.api.streaming.internal_protocols import (
    TaskStreamChannelDeregistrationProtocol,
)
from features.api.streaming.stream_listener_cleanup import cleanup_stream_listener
from features.api.streaming.task_stream_channel_broadcast import (
    broadcast_event,
    flush_chunk_batch,
)
from features.api.streaming.task_stream_channel_listeners import (
    create_stream_subscription,
)
from features.api.streaming.task_stream_channel_pump import run_pump_loop
from features.api.streaming.task_stream_channel_terminal_retention import (
    TaskStreamTerminalRetention,
)
from features.api.streaming.task_stream_subscription import StreamSubscription

__all__ = ("TaskStreamChannel",)

LOGGER_NAME = "SoAI.features.api.task_stream_channel"


class TaskStreamChannel:
    def __init__(
        self,
        reply_queue: asyncio.Queue[Event],
        shutdown_event: asyncio.Event,
        *,
        registry: TaskStreamChannelDeregistrationProtocol,
        task_registry: TaskRegistryProtocol,
        cancellation_binder: TaskCancellationBinderProtocol,
        finalizer_tracker: TaskFinalizerTrackerProtocol,
        buffer_limit: int,
        listener_size: int,
        terminal_retention_seconds: float,
        metrics_manager: MetricsManagerProtocol | None = None,
    ) -> None:
        logger = get_logger(LOGGER_NAME)
        self.registry = registry
        self.reply_queue = reply_queue
        self.shutdown_event = shutdown_event
        self.task_registry = task_registry
        self.cancellation_binder = cancellation_binder
        self.finalizer_tracker = finalizer_tracker
        self.buffer: deque[Event] = deque(maxlen=max(1, buffer_limit))
        self._listener_maxsize = max(1, listener_size)
        self.listeners: dict[str, asyncio.Queue[Event | None]] = {}
        self.pending_chunk_deliveries: dict[str, asyncio.Task[None]] = {}
        self.pending_chunk_queues: dict[str, asyncio.Queue[StreamChunkEvent]] = {}
        self.lock = asyncio.Lock()
        self.is_closed = False
        self.task_id: str | None = None
        self.metrics_manager = metrics_manager
        self.terminal_retention = TaskStreamTerminalRetention(
            retention_seconds=terminal_retention_seconds,
        )
        self.pump_task = spawn_tracked_task(
            self.pump_loop(),
            name=f"task-stream-channel-{id(reply_queue):x}",
            logger=logger,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            cancellation_id=build_soai_id(
                (
                    "sys",
                    "streaming",
                    "pump",
                    safe_or_hashed_segment(f"{id(reply_queue):x}"),
                ),
            ),
            owner="task_stream_channel",
        )

    def set_task_id(self, task_id: str) -> None:
        self.task_id = task_id

    async def unregister_listener(self, listener_id: str) -> None:
        await cleanup_stream_listener(
            listener_id=listener_id,
            lock=self.lock,
            listeners=self.listeners,
            pending_chunk_deliveries=self.pending_chunk_deliveries,
            pending_chunk_queues=self.pending_chunk_queues,
            skip_current_task=False,
        )

    async def subscribe(self) -> StreamSubscription:
        return await create_stream_subscription(
            self,
            lock=self.lock,
            buffer=self.buffer,
            listener_maxsize=self._listener_maxsize,
            listeners=self.listeners,
        )

    async def broadcast(self, event: Event | None) -> None:
        await broadcast_event(self, event)

    async def flush_chunk_batch(self, chunk_batcher: StreamChunkBatcher) -> None:
        await flush_chunk_batch(self, chunk_batcher)

    async def pump_loop(self) -> None:
        await run_pump_loop(self)
