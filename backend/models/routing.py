"""SoAI - Routing publisher for virtual model configuration changes [backend/models/routing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.events.completion_waiting import (
    EventPublicationReceipt,
    await_publication_receipt,
)
from core.events.protocols import EventBusProtocol
from core.events.types_models_routing_events import RoutingConfigChangedEvent
from core.orchestrator.routing_config import RoutingConfigHolder

if TYPE_CHECKING:
    from core.orchestrator.routing_config import VirtualModelConfig

__all__ = (
    "ModelRoutingPublisher",
    "ModelRoutingPublisherDependencies",
)


class ModelRoutingPublisher:

    def __init__(self, deps: ModelRoutingPublisherDependencies) -> None:
        self.bus = deps.bus
        self._routing_config_holder = deps.routing_config_holder
        self._get_all_virtual_models = deps.virtual_model_get_all

    async def publish(self) -> None:
        base_routing_config = self._routing_config_holder.base_routing_config
        database_virtual_models = await self._get_all_virtual_models()
        updated_config = self._routing_config_holder.replace_database_virtual_models(
            database_virtual_models,
        )
        receipt = EventPublicationReceipt.create(
            event_type=RoutingConfigChangedEvent.__name__,
            operation="models.routing.publish",
        )
        await self.bus.publish(
            RoutingConfigChangedEvent(
                virtual_models=list(updated_config.virtual_models),
                failovers=list(base_routing_config.failovers),
                routing_config=base_routing_config,
            ),
            wait_for_completion=receipt.completion_signal,
        )
        await await_publication_receipt(receipt)


@dataclass(frozen=True, slots=True)
class ModelRoutingPublisherDependencies:
    bus: EventBusProtocol
    routing_config_holder: RoutingConfigHolder
    virtual_model_get_all: Callable[[], Awaitable[list[VirtualModelConfig]]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ModelRoutingPublisherDependencies",
            bus=self.bus,
            routing_config_holder=self.routing_config_holder,
            virtual_model_get_all=self.virtual_model_get_all,
        )
