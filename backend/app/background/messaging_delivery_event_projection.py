"""SoAI - Durable conversation event projection into Messaging deliveries [backend/app/background/messaging_delivery_event_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.events.types_base import Event
from core.events.types_conversation_durable import (
    ConversationControlCompletedEvent,
    ConversationInputTerminalEvent,
    ConversationInteractionRequiredEvent,
)

if TYPE_CHECKING:
    from core.events.protocols import DurableEventDeliveryProtocol
    from core.messaging.protocols import DatabaseMessagingDeliveriesProtocol

__all__ = (
    "MessagingDeliveryEventProjection",
    "MessagingDeliveryEventProjectionDependencies",
)


@dataclass(frozen=True, slots=True)
class MessagingDeliveryEventProjectionDependencies:
    durable_delivery: DurableEventDeliveryProtocol
    database_deliveries: DatabaseMessagingDeliveriesProtocol
    wake_event: asyncio.Event

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MessagingDeliveryEventProjectionDependencies",
            durable_delivery=self.durable_delivery,
            database_deliveries=self.database_deliveries,
            wake_event=self.wake_event,
        )


class MessagingDeliveryEventProjection:
    def __init__(self, deps: MessagingDeliveryEventProjectionDependencies) -> None:
        self._deps = deps
        self._subscribed = False

    async def _project_terminal_event(self, event: Event) -> None:
        if not isinstance(event, ConversationInputTerminalEvent):
            return
        await self._deps.database_deliveries.project_terminal_event(event)
        self._deps.wake_event.set()

    async def _project_control_event(self, event: Event) -> None:
        if not isinstance(event, ConversationControlCompletedEvent):
            return
        await self._deps.database_deliveries.project_control_event(event)
        self._deps.wake_event.set()

    async def _project_interaction_event(self, event: Event) -> None:
        if not isinstance(event, ConversationInteractionRequiredEvent):
            return
        await self._deps.database_deliveries.project_interaction_event(event)
        self._deps.wake_event.set()

    def subscribe(self) -> None:
        if self._subscribed:
            return
        self._deps.durable_delivery.subscribe(
            ConversationInputTerminalEvent,
            self._project_terminal_event,
        )
        self._deps.durable_delivery.subscribe(
            ConversationControlCompletedEvent,
            self._project_control_event,
        )
        self._deps.durable_delivery.subscribe(
            ConversationInteractionRequiredEvent,
            self._project_interaction_event,
        )
        self._subscribed = True

    def unsubscribe(self) -> None:
        if not self._subscribed:
            return
        self._deps.durable_delivery.unsubscribe(
            ConversationControlCompletedEvent,
            self._project_control_event,
        )
        self._deps.durable_delivery.unsubscribe(
            ConversationInteractionRequiredEvent,
            self._project_interaction_event,
        )
        self._deps.durable_delivery.unsubscribe(
            ConversationInputTerminalEvent,
            self._project_terminal_event,
        )
        self._subscribed = False
