"""SoAI - Streaming subsystem protocol definitions [backend/core/streaming/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Protocol

from core.config.protocols import ConfigProtocol
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.runtime.protocols import RequestContextProtocol
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationHistoryProtocol,
    TaskRegistryProtocol,
)
from core.tasks.task import Task
from core.types.json import JSONDict

__all__ = (
    "CreateAdditionalTaskCallback",
    "CreateStreamGeneratorCallback",
    "StreamDependenciesProtocol",
    "StreamGeneratorStateProtocol",
    "StreamSubscriptionProtocol",
)


class StreamDependenciesProtocol(Protocol):
    @property
    def config(self) -> ConfigProtocol: ...

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    def cancellation_coordinator(self) -> CancellationCoordinatorProtocol: ...

    @property
    def cancellation_history(self) -> CancellationHistoryProtocol: ...

    @property
    def event_bus(self) -> EventBusProtocol: ...

    @property
    def shutdown_event(self) -> asyncio.Event: ...


class StreamSubscriptionProtocol(Protocol):
    @property
    def listener_id(self) -> str: ...

    @property
    def queue(self) -> asyncio.Queue[Event | None]: ...

    async def close(self) -> None: ...


class StreamGeneratorStateProtocol(Protocol):
    payload: JSONDict | None
    partial_payload: JSONDict | None
    done_sent: bool
    stream_successful: bool
    usage: JSONDict | None


class CreateAdditionalTaskCallback(Protocol):
    def __call__(
        self,
        payload: JSONDict,
        iteration_context: RequestContextProtocol,
        effective_cancellation_id: str,
        on_bytes: Callable[[bytes], Awaitable[None] | None],
    ) -> Awaitable[tuple[Task, asyncio.Queue[Event]]]: ...


class CreateStreamGeneratorCallback(Protocol):
    def __call__(
        self,
        reply_queue: asyncio.Queue[Event],
        stream_context: RequestContextProtocol,
        task: Task,
        stream_state: StreamGeneratorStateProtocol,
        stream_transcript: OpenAIStreamTranscript,
    ) -> AsyncIterator[bytes]: ...
