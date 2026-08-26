"""SoAI - Orchestrated task recovery dependencies [backend/orchestrator/control/task_recovery_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.tasks.protocols import CancellationHistoryProtocol, TaskRegistryProtocol
from core.tasks.protocols_query import TaskRegistryQueryView
from orchestrator.internal_protocols import (
    OrchestratorActiveInferenceProtocol,
    OrchestratorTaskOutcomesProtocol,
)
from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("OrchestratedTaskRecoveryDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratedTaskRecoveryDependencies:
    queue: QueueServiceView
    active_inferences: OrchestratorActiveInferenceProtocol
    outcomes: OrchestratorTaskOutcomesProtocol
    task_registry: TaskRegistryProtocol
    task_registry_queries: TaskRegistryQueryView
    cancellation_history: CancellationHistoryProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratedTaskRecoveryDependencies",
            active_inferences=self.active_inferences,
            cancellation_history=self.cancellation_history,
            outcomes=self.outcomes,
            queue=self.queue,
            task_registry=self.task_registry,
            task_registry_queries=self.task_registry_queries,
        )
