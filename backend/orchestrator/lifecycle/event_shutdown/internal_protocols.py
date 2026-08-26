"""SoAI - Orchestrator lifecycle watcher and shutdown dependency protocols [backend/orchestrator/lifecycle/event_shutdown/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.orchestrator.protocols_lifecycle import OrchestratorLifecyclePublisherProtocol
from core.state.protocols_publication import RuntimeStatePublicationSideEffectsProtocol
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.lifecycle.state_access.internal_protocols import (
    LifecycleStateAccessorProtocol,
)

if TYPE_CHECKING:
    from orchestrator.internal_protocols import OrchestratorCapacityProtocol
    from orchestrator.types import OrchestratorDependencies

__all__ = (
    "OrchestratorShutdownStopLogicDependenciesProtocol",
    "OrchestratorWatcherEventDependenciesProtocol",
    "OrchestratorWatcherEventHandlerProtocol",
    "ShutdownExecutionDependenciesProtocol",
)


class OrchestratorWatcherEventDependenciesProtocol(Protocol):
    @property
    def orchestrator(self) -> OrchestratorDependencies: ...

    @property
    def capacity(self) -> OrchestratorCapacityProtocol: ...

    @property
    def state(self) -> LifecycleStateAccessorProtocol: ...

    @property
    def lifecycle_publisher(self) -> OrchestratorLifecyclePublisherProtocol: ...

    @property
    def runtime_state_side_effects(self) -> RuntimeStatePublicationSideEffectsProtocol: ...


class OrchestratorShutdownStopLogicDependenciesProtocol(Protocol):
    @property
    def orchestrator(self) -> OrchestratorDependencies: ...

    @property
    def lifecycle_publisher(self) -> OrchestratorLifecyclePublisherProtocol: ...


class ShutdownExecutionDependenciesProtocol(Protocol):
    @property
    def orchestrator(self) -> OrchestratorDependencies: ...

    @property
    def capacity(self) -> OrchestratorCapacityProtocol: ...

    @property
    def task_registry(self) -> TaskRegistryProtocol: ...

    @property
    def state(self) -> LifecycleStateAccessorProtocol: ...

    @property
    def lifecycle_publisher(self) -> OrchestratorLifecyclePublisherProtocol: ...


class OrchestratorWatcherEventHandlerProtocol(Protocol):
    deps: OrchestratorWatcherEventDependenciesProtocol

    async def discard_plugin_runtime_mutations(self, plugin_name: str) -> None: ...
