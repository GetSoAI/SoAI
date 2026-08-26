"""SoAI - Orchestrator lifecycle dependencies [backend/orchestrator/lifecycle/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.orchestrator.routing_config import RoutingConfig
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.state.protocols import AuthoritativePluginStateTransitionsProtocol
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.internal_protocols import (
    OrchestratorCapacityProtocol,
    VirtualModelHealthProtocol,
    VirtualModelRotationProtocol,
)
from orchestrator.lifecycle.state_access.internal_protocols import (
    LifecycleStateAccessorProtocol,
)
from orchestrator.types import OrchestratorDependencies

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("OrchestratorLifecycleDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleDependencies:
    orchestrator: OrchestratorDependencies
    config: OrchestratorRuntimeConfig
    routing_config: RoutingConfig
    capacity: OrchestratorCapacityProtocol
    virtual_model_health: VirtualModelHealthProtocol
    virtual_model_rotation: VirtualModelRotationProtocol
    task_registry: TaskRegistryProtocol
    shutdown_event: asyncio.Event
    tool_name_extractor: Callable[[list[JSONValue]], list[str]]
    state_accessor: LifecycleStateAccessorProtocol
    authoritative_plugin_state_transitions: AuthoritativePluginStateTransitionsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorLifecycleDependencies",
            capacity=self.capacity,
            config=self.config,
            orchestrator=self.orchestrator,
            routing_config=self.routing_config,
            shutdown_event=self.shutdown_event,
            state_accessor=self.state_accessor,
            authoritative_plugin_state_transitions=self.authoritative_plugin_state_transitions,
            task_registry=self.task_registry,
            tool_name_extractor=self.tool_name_extractor,
            virtual_model_health=self.virtual_model_health,
            virtual_model_rotation=self.virtual_model_rotation,
        )
