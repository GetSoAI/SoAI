"""SoAI - Routing config event types [backend/core/events/types_models_routing_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.events.types_base import Event
from core.orchestrator.routing_config import (
    FailoverConfig,
    RoutingConfig,
    VirtualModelConfig,
)

__all__ = ("RoutingConfigChangedEvent",)


@dataclass(slots=True)
class RoutingConfigChangedEvent(Event):
    virtual_models: list[VirtualModelConfig]
    failovers: list[FailoverConfig]
    routing_config: RoutingConfig | None = None
