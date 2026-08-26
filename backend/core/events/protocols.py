"""SoAI - Event bus runtime protocols for partitioning and delivery [backend/core/events/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from core.events.types_base import Event, EventDelivery

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Awaitable, Callable

__all__ = (
    "ConvIdPartitionKeyProtocol",
    "DurableEventDeliveryProtocol",
    "EventBusProtocol",
    "EventCompletionSignal",
    "EventSubscriptionProtocol",
    "EventWithDeliveryProtocol",
    "PluginPartitionKeyProtocol",
)


@runtime_checkable
class EventSubscriptionProtocol(Protocol):
    def subscribe(
        self,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> None: ...

    def unsubscribe(
        self,
        event_type: type[Event],
        callback: Callable[[Event], Awaitable[None]],
    ) -> None: ...

    def has_subscribers(self, event_type: type[Event]) -> bool: ...


@runtime_checkable
class EventCompletionSignal(Protocol):
    async def wait(self) -> bool | None: ...

    def is_set(self) -> bool: ...


@runtime_checkable
class EventBusProtocol(EventSubscriptionProtocol, Protocol):
    shutdown_event: asyncio.Event

    async def publish(
        self,
        event: Event,
        wait_for_completion: EventCompletionSignal | None = None,
    ) -> None: ...

    def try_publish_nowait(
        self,
        event: Event,
        wait_for_completion: EventCompletionSignal | None = None,
    ) -> bool: ...

    def start(self) -> None: ...

    async def shutdown(self) -> None: ...


@runtime_checkable
class DurableEventDeliveryProtocol(EventSubscriptionProtocol, Protocol):
    async def deliver(self, event: Event, *, timeout_sec: float | None = None) -> None: ...


@runtime_checkable
class EventWithDeliveryProtocol(Protocol):
    delivery: EventDelivery


@runtime_checkable
class ConvIdPartitionKeyProtocol(Protocol):
    user_id: int
    conv_id: str


@runtime_checkable
class PluginPartitionKeyProtocol(Protocol):
    @property
    def partition_plugin_name(self) -> str: ...
