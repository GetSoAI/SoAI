"""SoAI - Task stream channel broadcast methods [backend/features/api/streaming/task_stream_channel_broadcast.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.types_base import Event
from core.events.types_models_streaming import StreamChunkEvent
from core.metrics.keyspace_paths_event_streaming import (
    STREAMING_COUNTER_CHUNKS_COALESCED,
)
from features.api.streaming.channel_delivery import (
    broadcast_non_chunk,
    broadcast_stream_chunk,
)
from features.api.streaming.chunk_batcher import StreamChunkBatcher
from features.api.streaming.delivery_metrics import record_delivery_metric
from features.api.streaming.internal_protocols import TaskStreamChannelBroadcastProtocol
from features.api.streaming.terminal_events import is_terminal_task_stream_event

__all__ = (
    "broadcast_event",
    "flush_chunk_batch",
)


async def broadcast_event(self: TaskStreamChannelBroadcastProtocol, event: Event | None) -> None:
    is_terminal = event is None or is_terminal_task_stream_event(event)
    async with self.lock:
        listeners_snapshot = list(self.listeners.items())
    if not listeners_snapshot:
        return
    if isinstance(event, StreamChunkEvent):
        await broadcast_stream_chunk(
            listeners_snapshot,
            event,
            self.shutdown_event,
            self.task_id,
            self.metrics_manager,
            self.lock,
            self.listeners,
            self.pending_chunk_deliveries,
            self.pending_chunk_queues,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
        )
        return
    await broadcast_non_chunk(
        listeners_snapshot,
        event,
        is_terminal,
        self.shutdown_event,
        self.task_id,
        self.metrics_manager,
        self.lock,
        self.listeners,
        self.pending_chunk_deliveries,
        self.pending_chunk_queues,
    )


async def flush_chunk_batch(
    self: TaskStreamChannelBroadcastProtocol,
    chunk_batcher: StreamChunkBatcher,
) -> None:
    if not chunk_batcher.has_pending():
        return
    pending_count = chunk_batcher.pending_count()
    coalesced_event = chunk_batcher.flush()
    if coalesced_event is None:
        return
    if pending_count > 1:
        record_delivery_metric(
            self.metrics_manager,
            STREAMING_COUNTER_CHUNKS_COALESCED,
            pending_count,
        )
    async with self.lock:
        self.buffer.append(coalesced_event)
    await self.broadcast(coalesced_event)
