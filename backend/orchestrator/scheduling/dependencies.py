"""SoAI - Dependency bundle for orchestrator scheduling service [backend/orchestrator/scheduling/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.models.protocols import (
    ModelInformationServiceProtocol,
    ModelResolutionServiceProtocol,
)
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.orchestrator.routing_config import RoutingConfig
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.state.protocols import StateAggregatorProtocol
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.internal_protocols import (
    OrchestratorCapacityProtocol,
    OrchestratorInferenceExecutorProtocol,
    OrchestratorTaskOutcomesProtocol,
    TransientFailureCooldownsProtocol,
    VirtualModelHealthProtocol,
    VirtualModelRotationProtocol,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.types import OrchestratorDependencies

__all__ = (
    "OrchestratorSchedulerDependencies",
    "SchedulerDispatchCandidateDependencies",
    "SchedulerPlanningDependencies",
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from core.orchestrator.scheduler_work import SchedulerWorkItem
    from core.tasks.task import Task


@dataclass(frozen=True, slots=True)
class OrchestratorSchedulerDependencies:
    orchestrator: OrchestratorDependencies
    config: OrchestratorRuntimeConfig
    routing_config: RoutingConfig
    queue: OrchestratorQueueProtocol
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    inference_executor: OrchestratorInferenceExecutorProtocol
    outcomes: OrchestratorTaskOutcomesProtocol
    capacity: OrchestratorCapacityProtocol
    transient_failures: TransientFailureCooldownsProtocol
    virtual_model_health: VirtualModelHealthProtocol
    virtual_model_rotation: VirtualModelRotationProtocol
    task_registry: TaskRegistryProtocol
    shutdown_event: asyncio.Event

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorSchedulerDependencies",
            capacity=self.capacity,
            config=self.config,
            inference_executor=self.inference_executor,
            lifecycle=self.lifecycle,
            orchestrator=self.orchestrator,
            outcomes=self.outcomes,
            queue=self.queue,
            routing_config=self.routing_config,
            shutdown_event=self.shutdown_event,
            task_registry=self.task_registry,
            transient_failures=self.transient_failures,
            virtual_model_health=self.virtual_model_health,
            virtual_model_rotation=self.virtual_model_rotation,
        )


@dataclass(frozen=True, slots=True)
class SchedulerDispatchCandidateDependencies:
    orchestrator: OrchestratorDependencies
    queue: OrchestratorQueueProtocol
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    outcomes: OrchestratorTaskOutcomesProtocol
    queue_scheduler_work: Callable[[SchedulerWorkItem], Coroutine[None, None, None]]
    schedule_plugin_dispatch: Callable[[Task, str], Coroutine[None, None, None]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SchedulerDispatchCandidateDependencies",
            lifecycle=self.lifecycle,
            orchestrator=self.orchestrator,
            outcomes=self.outcomes,
            queue=self.queue,
            queue_scheduler_work=self.queue_scheduler_work,
            schedule_plugin_dispatch=self.schedule_plugin_dispatch,
        )


@dataclass(frozen=True, slots=True)
class SchedulerPlanningDependencies:
    queue: OrchestratorQueueProtocol
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    transient_failures: TransientFailureCooldownsProtocol
    virtual_model_health: VirtualModelHealthProtocol
    virtual_model_rotation: VirtualModelRotationProtocol
    capacity: OrchestratorCapacityProtocol
    model_information_service: ModelInformationServiceProtocol
    model_resolution_service: ModelResolutionServiceProtocol
    state_aggregator: StateAggregatorProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SchedulerPlanningDependencies",
            capacity=self.capacity,
            lifecycle=self.lifecycle,
            model_information_service=self.model_information_service,
            model_resolution_service=self.model_resolution_service,
            queue=self.queue,
            state_aggregator=self.state_aggregator,
            transient_failures=self.transient_failures,
            virtual_model_health=self.virtual_model_health,
            virtual_model_rotation=self.virtual_model_rotation,
        )
