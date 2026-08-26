"""SoAI - Dependency bundle for lifecycle user command handlers [backend/orchestrator/lifecycle/user_commands/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.orchestrator.protocols_lifecycle import (
    OrchestratorCircuitBreakersProtocol,
    OrchestratorLifecyclePublisherProtocol,
    OrchestratorWatchersProtocol,
)
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleShutdownCoordinatorProtocol,
)
from orchestrator.types import OrchestratorDependencies

__all__ = ("OrchestratorLifecycleUserCommandsDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorLifecycleUserCommandsDependencies:
    orchestrator: OrchestratorDependencies
    task_registry: TaskRegistryProtocol
    watchers: OrchestratorWatchersProtocol
    lifecycle_publisher: OrchestratorLifecyclePublisherProtocol
    circuit_breakers: OrchestratorCircuitBreakersProtocol
    shutdown: OrchestratorLifecycleShutdownCoordinatorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorLifecycleUserCommandsDependencies",
            circuit_breakers=self.circuit_breakers,
            lifecycle_publisher=self.lifecycle_publisher,
            orchestrator=self.orchestrator,
            shutdown=self.shutdown,
            task_registry=self.task_registry,
            watchers=self.watchers,
        )
