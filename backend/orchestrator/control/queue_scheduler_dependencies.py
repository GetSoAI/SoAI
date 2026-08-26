"""SoAI - Shared control queue scheduler dependencies [backend/orchestrator/control/queue_scheduler_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.orchestrator.protocols_scheduler import OrchestratorSchedulerProtocol
from orchestrator.internal_protocols import (
    OrchestratorActiveInferenceProtocol,
    OrchestratorTaskOutcomesProtocol,
)
from orchestrator.queueing.internal_protocols import QueueServiceView
from orchestrator.types import OrchestratorDependencies

__all__ = ("ControlQueueSchedulerDependencies",)


@dataclass(frozen=True, slots=True)
class ControlQueueSchedulerDependencies:
    orchestrator: OrchestratorDependencies
    queue: QueueServiceView
    scheduler: OrchestratorSchedulerProtocol
    active_inferences: OrchestratorActiveInferenceProtocol
    outcomes: OrchestratorTaskOutcomesProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ControlQueueSchedulerDependencies",
            active_inferences=self.active_inferences,
            orchestrator=self.orchestrator,
            outcomes=self.outcomes,
            queue=self.queue,
            scheduler=self.scheduler,
        )
