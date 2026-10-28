"""SoAI - Streaming subsystem protocol definitions [backend/core/streaming/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import Protocol

from core.config.protocols import ConfigProtocol
from core.errors.payload import ErrorPublicPayload
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.tasks.protocols import (
    CancellationCoordinatorProtocol,
    CancellationHistoryProtocol,
    TaskRegistryProtocol,
)
from core.types.json import JSONDict

__all__ = (
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
    public_error: ErrorPublicPayload | None
