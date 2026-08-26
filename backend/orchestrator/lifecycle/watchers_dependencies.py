"""SoAI - Dependency bundle for orchestrator lifecycle watchers [backend/orchestrator/lifecycle/watchers_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.orchestrator.protocols_lifecycle import OrchestratorLifecyclePublisherProtocol
from core.state.protocols_publication import RuntimeStatePublicationSideEffectsProtocol
from orchestrator.internal_protocols import OrchestratorCapacityProtocol
from orchestrator.lifecycle.state_access.internal_protocols import (
    LifecycleStateAccessorProtocol,
)
from orchestrator.types import OrchestratorDependencies

__all__ = ("OrchestratorLifecycleWatchersDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleWatchersDependencies:
    orchestrator: OrchestratorDependencies
    capacity: OrchestratorCapacityProtocol
    state: LifecycleStateAccessorProtocol
    lifecycle_publisher: OrchestratorLifecyclePublisherProtocol
    runtime_state_side_effects: RuntimeStatePublicationSideEffectsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorLifecycleWatchersDependencies",
            capacity=self.capacity,
            lifecycle_publisher=self.lifecycle_publisher,
            orchestrator=self.orchestrator,
            runtime_state_side_effects=self.runtime_state_side_effects,
            state=self.state,
        )
