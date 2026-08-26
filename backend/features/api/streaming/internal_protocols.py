"""SoAI - API streaming internal protocols [backend/features/api/streaming/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections import deque
from typing import TYPE_CHECKING, Protocol

from core.app.protocols import ApplicationControlProtocol
from core.config.protocols import ConfigProtocol
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.events.types_models_streaming import StreamChunkEvent
from core.metrics.protocols import MetricsManagerProtocol
from core.streaming.protocols import (
    StreamDependenciesProtocol,
    StreamSubscriptionProtocol,
)
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from core.tool_calls.protocols import ToolCallProcessingProtocol
from features.api.streaming.chunk_batcher import StreamChunkBatcher
from features.api.streaming.task_stream_channel_terminal_retention import (
    TaskStreamTerminalRetention,
)

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter

__all__ = (
    "OpenAIStreamApiDependenciesProtocol",
    "StreamDependenciesSourceProtocol",
    "TaskIdContextProtocol",
    "TaskStreamChannelBroadcastProtocol",
    "TaskStreamChannelDeregistrationProtocol",
    "TaskStreamChannelListenerProtocol",
    "TaskStreamChannelProtocol",
    "TaskStreamChannelPumpProtocol",
    "TaskStreamChannelRegistryProtocol",
)


class TaskStreamChannelDeregistrationProtocol(Protocol):
    async def discard(self, reply_queue: asyncio.Queue[Event]) -> None: ...


class TaskStreamChannelListenerProtocol(Protocol):
    async def unregister_listener(self, listener_id: str) -> None: ...


class TaskStreamChannelProtocol(Protocol):
    is_closed: bool

    async def unregister_listener(self, listener_id: str) -> None: ...


class TaskStreamChannelBroadcastProtocol(Protocol):
    shutdown_event: asyncio.Event
    metrics_manager: MetricsManagerProtocol | None
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    buffer: deque[Event]
    lock: asyncio.Lock
    listeners: dict[str, asyncio.Queue[Event | None]]
    pending_chunk_deliveries: dict[str, asyncio.Task[None]]
    pending_chunk_queues: dict[str, asyncio.Queue[StreamChunkEvent]]
    task_id: str | None

    async def broadcast(self, event: Event | None) -> None: ...


class TaskStreamChannelPumpProtocol(TaskStreamChannelBroadcastProtocol, Protocol):
    reply_queue: asyncio.Queue[Event]
    registry: TaskStreamChannelDeregistrationProtocol
    task_registry: TaskRegistryProtocol
    terminal_retention: TaskStreamTerminalRetention
    is_closed: bool

    async def flush_chunk_batch(self, chunk_batcher: StreamChunkBatcher) -> None: ...


class TaskStreamChannelRegistryProtocol(Protocol):
    async def acquire_stream_subscription(
        self,
        reply_queue: asyncio.Queue[Event],
        *,
        shutdown_event: asyncio.Event,
        task_registry: TaskRegistryProtocol,
        config: ConfigProtocol,
        metrics_manager: MetricsManagerProtocol | None,
        cancellation_binder: TaskCancellationBinderProtocol,
        finalizer_tracker: TaskFinalizerTrackerProtocol,
        task_id: str | None = None,
    ) -> StreamSubscriptionProtocol: ...


class StreamDependenciesSourceProtocol(StreamDependenciesProtocol, Protocol):
    @property
    def stream_channel_registry(self) -> TaskStreamChannelRegistryProtocol: ...

    @property
    def task_cancellation_binder(self) -> TaskCancellationBinderProtocol: ...

    @property
    def task_finalizer_tracker(self) -> TaskFinalizerTrackerProtocol: ...

    @property
    def prompt_token_counter(self) -> PromptTokenCounter: ...

    @property
    def metrics_manager(self) -> MetricsManagerProtocol | None: ...


class OpenAIStreamApiDependenciesProtocol(Protocol):
    @property
    def tool_call_processor(self) -> ToolCallProcessingProtocol: ...

    @property
    def event_bus(self) -> EventBusProtocol: ...

    @property
    def application_control(self) -> ApplicationControlProtocol: ...


class TaskIdContextProtocol(Protocol):
    task_id: str | None
