"""SoAI - Task stream channel registry [backend/features/api/streaming/stream_channel_registry.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.types_base import Event
from core.metrics.protocols import MetricsManagerProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from core.validation.integers import is_strict_int
from features.api.streaming.task_stream_channel import TaskStreamChannel
from features.api.streaming.task_stream_channel_retention_config import (
    resolve_post_terminal_retention_seconds,
)
from features.api.streaming.task_stream_subscription import StreamSubscription

__all__ = (
    "TaskStreamChannelRegistry",
    "TaskStreamChannelRegistryDependencies",
)


@dataclass(frozen=True, slots=True)
class TaskStreamChannelRegistryDependencies:
    def __post_init__(self) -> None:
        require_dependencies(owner="TaskStreamChannelRegistryDependencies")


class TaskStreamChannelRegistry:
    __slots__ = ("_channels", "_deps", "_lock")

    def __init__(self, deps: TaskStreamChannelRegistryDependencies) -> None:
        self._deps = deps
        self._channels: dict[asyncio.Queue[Event], TaskStreamChannel] = {}
        self._lock: asyncio.Lock | None = None

    def _ensure_lock(self) -> asyncio.Lock:
        lock = self._lock
        if lock is None:
            lock = asyncio.Lock()
            self._lock = lock
        return lock

    async def discard(self, reply_queue: asyncio.Queue[Event]) -> None:
        lock = self._ensure_lock()
        async with lock:
            existing = self._channels.get(reply_queue)
            if existing is not None and existing.is_closed:
                self._channels.pop(reply_queue, None)

    def _resolve_stream_buffer_limit(
        self,
        reply_queue: asyncio.Queue[Event],
        config: ConfigProtocol,
    ) -> int:
        configured_limit = config.get_int("SERVER.HTTP.STREAMING.REPLAY_BUFFER_SIZE")
        if is_strict_int(configured_limit) and configured_limit > 0:
            return configured_limit
        try:
            queue_limit = reply_queue.maxsize
        except AttributeError:
            queue_limit = 0
        if is_strict_int(queue_limit) and queue_limit > 0:
            return max(queue_limit, 100)
        return 1000

    def _resolve_listener_queue_size(
        self,
        reply_queue: asyncio.Queue[Event],
        buffer_limit: int,
    ) -> int:
        try:
            queue_limit = reply_queue.maxsize
        except AttributeError:
            queue_limit = 0
        if is_strict_int(queue_limit) and queue_limit > 0:
            return max(1, min(int(queue_limit), int(buffer_limit)))
        return max(1, int(buffer_limit))

    def _resolve_terminal_retention_seconds(self, config: ConfigProtocol) -> float:
        return resolve_post_terminal_retention_seconds(config)

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
    ) -> StreamSubscription:
        lock = self._ensure_lock()
        async with lock:
            channel = self._channels.get(reply_queue)
            if channel is None:
                limit = self._resolve_stream_buffer_limit(reply_queue, config)
                listener_size = self._resolve_listener_queue_size(reply_queue, limit)
                channel = TaskStreamChannel(
                    reply_queue,
                    shutdown_event,
                    registry=self,
                    task_registry=task_registry,
                    cancellation_binder=cancellation_binder,
                    finalizer_tracker=finalizer_tracker,
                    buffer_limit=limit,
                    listener_size=listener_size,
                    terminal_retention_seconds=self._resolve_terminal_retention_seconds(config),
                    metrics_manager=metrics_manager,
                )
                if task_id:
                    channel.set_task_id(task_id)
                self._channels[reply_queue] = channel
            elif task_id and (not channel.task_id):
                channel.set_task_id(task_id)
        return await channel.subscribe()
