"""SoAI - Shared streaming types [backend/features/api/streaming/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.errors.exceptions import ValidationError
from core.events.protocols import EventBusProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationHistoryProtocol,
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
    TaskRegistryProtocol,
)
from features.api.streaming.internal_protocols import TaskStreamChannelRegistryProtocol

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.openai.token_counter import PromptTokenCounter
    from core.streaming.protocols import StreamSubscriptionProtocol

__all__ = ("StreamDependencies",)


@dataclass(frozen=True, slots=True)
class StreamDependencies:
    config: ConfigProtocol
    task_registry: TaskRegistryProtocol
    cancellation_coordinator: CancellationCoordinatorProtocol
    cancellation_history: CancellationHistoryProtocol
    event_bus: EventBusProtocol
    shutdown_event: asyncio.Event
    stream_channel_registry: TaskStreamChannelRegistryProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    prompt_token_counter: PromptTokenCounter
    metrics_manager: MetricsManagerProtocol | None = field(default=None)

    def __post_init__(self) -> None:
        require_dependencies(
            owner="StreamDependencies",
            cancellation_binder=self.cancellation_binder,
            cancellation_coordinator=self.cancellation_coordinator,
            cancellation_history=self.cancellation_history,
            config=self.config,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            prompt_token_counter=self.prompt_token_counter,
            shutdown_event=self.shutdown_event,
            stream_channel_registry=self.stream_channel_registry,
            task_registry=self.task_registry,
        )
        for attribute_name, attribute in (
            ("get", self.config.get),
            ("get_int", self.config.get_int),
            ("get_float", self.config.get_float),
            ("get_bool", self.config.get_bool),
            ("get_str", self.config.get_str),
        ):
            if not callable(attribute):
                raise ValidationError(
                    "StreamDependencies.config must provide typed config accessors.",
                    details={
                        "missing": attribute_name,
                        "actual_type": type(self.config).__name__,
                    },
                )

    async def acquire_stream_subscription(
        self,
        reply_queue: asyncio.Queue[Event],
        *,
        task_id: str | None,
    ) -> StreamSubscriptionProtocol:
        return await self.stream_channel_registry.acquire_stream_subscription(
            reply_queue,
            shutdown_event=self.shutdown_event,
            task_registry=self.task_registry,
            config=self.config,
            metrics_manager=self.metrics_manager,
            cancellation_binder=self.cancellation_binder,
            finalizer_tracker=self.finalizer_tracker,
            task_id=task_id,
        )
