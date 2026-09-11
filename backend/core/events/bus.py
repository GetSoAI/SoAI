"""SoAI - Event bus with subscription and backpressure handling [backend/core/events/bus.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import override

from core.concurrency.queue_ops import QueueDropTracker
from core.errors.trace_logging import ensure_trace_logging
from core.events.bus_constructor import parse_event_bus_constructor_values
from core.events.bus_instance_init import initialize_event_bus_state
from core.events.bus_lifecycle_operation import (
    execute_event_bus_shutdown,
    execute_event_bus_start,
)
from core.events.bus_publish_operation import (
    execute_event_bus_publish,
    try_execute_event_bus_publish_nowait,
)
from core.events.bus_stuck_callback_registry import (
    EVENT_BUS_STUCK_CALLBACK_SHUTDOWN_CANCELLATION_WAIT_SEC,
    EventBusStuckCallbackRegistry,
)
from core.events.bus_subscriptions import (
    SubscriptionRegistry,
    SubscriptionRegistryDependencies,
)
from core.events.protocols import EventCompletionSignal
from core.events.types_base import Event
from core.lifecycle.protocols import Shutdownable
from core.logging.protocols import TraceLogger
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

__all__ = ("EventBus",)

LOGGER_NAME = "SoAI.core.events.bus"


_REPLY_CHANNEL_WARNING_INTERVAL_SECONDS: float = 30.0


class EventBus(Shutdownable):
    def __init__(
        self,
        *,
        cancellation_binder: TaskCancellationBinderProtocol,
        finalizer_tracker: TaskFinalizerTrackerProtocol,
        queue_size: int = 10000,
        num_workers: int = 4,
        metrics_recorder: MetricsManagerProtocol | None = None,
        publish_timeout_sec: float | None = None,
        backpressure_warning_depth: int | None = None,
        dispatch_timeout_sec: float | None = 30.0,
        shutdown_timeout_sec: float | None = None,
        per_callback_timeout_sec: float | None = 5.0,
    ) -> None:
        ensure_trace_logging()
        self._logger: TraceLogger = get_logger(LOGGER_NAME)
        self._subscriptions = SubscriptionRegistry(
            SubscriptionRegistryDependencies(logger=self._logger),
        )
        constructor_values = parse_event_bus_constructor_values(
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            queue_size=queue_size,
            num_workers=num_workers,
            publish_timeout_sec=publish_timeout_sec,
            backpressure_warning_depth=backpressure_warning_depth,
            dispatch_timeout_sec=dispatch_timeout_sec,
            shutdown_timeout_sec=shutdown_timeout_sec,
            per_callback_timeout_sec=per_callback_timeout_sec,
            logger=self._logger,
        )
        initialized_state = initialize_event_bus_state(
            constructor_values=constructor_values,
            metrics_recorder=metrics_recorder,
        )
        self._queue_size = initialized_state.queue_size
        self.num_workers = initialized_state.num_workers
        self._queue_max_per_worker = initialized_state.queue_max_per_worker
        self._aggregate_queue_max = initialized_state.aggregate_queue_max
        self._cancellation_binder = cancellation_binder
        self._finalizer_tracker = finalizer_tracker
        self._queues = initialized_state.queues
        self._round_robin_index = 0
        self._worker_tasks: list[asyncio.Task[None]] = []
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self.metrics_recorder = metrics_recorder
        self._publish_timeout = initialized_state.publish_timeout
        self._backpressure_warning_depth = initialized_state.backpressure_warning_depth
        self._dispatch_timeout = initialized_state.dispatch_timeout
        self._shutdown_timeout = initialized_state.shutdown_timeout
        self._per_callback_timeout = initialized_state.per_callback_timeout
        self._backpressure_tracker = initialized_state.backpressure_tracker
        self._reply_channel_drop_tracker = QueueDropTracker(_REPLY_CHANNEL_WARNING_INTERVAL_SECONDS)
        self._stuck_callback_registry = EventBusStuckCallbackRegistry()

    def set_metrics_recorder(self, recorder: MetricsManagerProtocol | None) -> None:
        self.metrics_recorder = recorder

    def subscribe(
        self,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> None:
        self._subscriptions.subscribe(
            event_type=event_type,
            callback=callback,
        )

    def unsubscribe(
        self,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> None:
        self._subscriptions.unsubscribe(
            event_type=event_type,
            callback=callback,
        )
        self._stuck_callback_registry.clear_quarantine(callback)

    def has_subscribers(self, event_type: type[Event]) -> bool:
        return self._subscriptions.has_subscribers(event_type)

    async def publish(
        self,
        event: Event,
        wait_for_completion: EventCompletionSignal | None = None,
    ) -> None:
        self._worker_tasks, self._round_robin_index = await execute_event_bus_publish(
            event=event,
            wait_for_completion=wait_for_completion,
            shutdown_event=self.shutdown_event,
            worker_tasks=self._worker_tasks,
            queues=self._queues,
            num_workers=self.num_workers,
            round_robin_index=self._round_robin_index,
            queue_size=self._queue_size,
            publish_timeout=self._publish_timeout,
            aggregate_queue_max=self._aggregate_queue_max,
            backpressure_tracker=self._backpressure_tracker,
            reply_channel_drop_tracker=self._reply_channel_drop_tracker,
            metrics_recorder=self.metrics_recorder,
            logger=self._logger,
        )

    def try_publish_nowait(
        self,
        event: Event,
        wait_for_completion: EventCompletionSignal | None = None,
    ) -> bool:
        published, self._worker_tasks, self._round_robin_index = (
            try_execute_event_bus_publish_nowait(
                event=event,
                wait_for_completion=wait_for_completion,
                shutdown_event=self.shutdown_event,
                worker_tasks=self._worker_tasks,
                queues=self._queues,
                num_workers=self.num_workers,
                round_robin_index=self._round_robin_index,
                queue_size=self._queue_size,
                backpressure_tracker=self._backpressure_tracker,
                reply_channel_drop_tracker=self._reply_channel_drop_tracker,
                metrics_recorder=self.metrics_recorder,
                logger=self._logger,
            )
        )
        return published

    def start(self) -> None:
        self._queues, self._worker_tasks, self._round_robin_index = execute_event_bus_start(
            worker_tasks=self._worker_tasks,
            shutdown_event=self.shutdown_event,
            queues=self._queues,
            num_workers=self.num_workers,
            queue_max_per_worker=self._queue_max_per_worker,
            metrics_recorder=self.metrics_recorder,
            collect_callbacks=self._subscriptions.collect_callbacks,
            dispatch_timeout=self._dispatch_timeout,
            per_callback_timeout=self._per_callback_timeout,
            logger=self._logger,
            cancellation_binder=self._cancellation_binder,
            finalizer_tracker=self._finalizer_tracker,
            stuck_callback_registry=self._stuck_callback_registry,
        )

    @override
    async def shutdown(self) -> None:
        self._queues, self._round_robin_index = await execute_event_bus_shutdown(
            shutdown_event=self.shutdown_event,
            queues=self._queues,
            worker_tasks=self._worker_tasks,
            shutdown_timeout=self._shutdown_timeout,
            num_workers=self.num_workers,
            queue_max_per_worker=self._queue_max_per_worker,
            logger=self._logger,
        )
        await self._stuck_callback_registry.cancel_pending(
            logger=self._logger,
            timeout_sec=EVENT_BUS_STUCK_CALLBACK_SHUTDOWN_CANCELLATION_WAIT_SEC,
        )
