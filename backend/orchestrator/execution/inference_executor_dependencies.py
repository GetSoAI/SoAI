"""SoAI - Orchestrator inference executor dependency bundle [backend/orchestrator/execution/inference_executor_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.orchestrator.routing_config import RoutingConfig
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from orchestrator.execution.internal_protocols import (
    ActiveInferenceRegistryProtocol,
    ExecutorEngineProtocol,
    InflightCancellationManagerProtocol,
    OutcomeManagerProtocol,
    ResultProcessorProtocol,
)
from orchestrator.types import OrchestratorDependencies

if TYPE_CHECKING:
    from core.tasks.protocols import TaskRegistryProtocol
    from orchestrator.lifecycle.service_interfaces.internal_protocols import (
        OrchestratorLifecycleCoordinatorProtocol,
    )
    from orchestrator.queueing.internal_protocols import QueueServiceView

__all__ = ("OrchestratorInferenceExecutorDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorInferenceExecutorDependencies:
    orchestrator: OrchestratorDependencies
    config: OrchestratorRuntimeConfig
    routing_config: RoutingConfig
    queue: QueueServiceView
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    task_registry: TaskRegistryProtocol
    active_inferences: ActiveInferenceRegistryProtocol
    cancellations: InflightCancellationManagerProtocol
    results: ResultProcessorProtocol
    engine: ExecutorEngineProtocol
    outcomes: OutcomeManagerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorInferenceExecutorDependencies",
            active_inferences=self.active_inferences,
            cancellations=self.cancellations,
            config=self.config,
            engine=self.engine,
            lifecycle=self.lifecycle,
            orchestrator=self.orchestrator,
            outcomes=self.outcomes,
            queue=self.queue,
            routing_config=self.routing_config,
            results=self.results,
            task_registry=self.task_registry,
        )
