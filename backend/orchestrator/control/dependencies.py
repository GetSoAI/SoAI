"""SoAI - Orchestrator control dependency container [backend/orchestrator/control/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.orchestrator.protocols_scheduler import OrchestratorSchedulerProtocol
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.plugins.dependencies import PluginGuardianDependencies
from core.plugins.protocols_guardian import PluginGuardianProtocol
from core.tasks.protocols import (
    CancelTaskCallable,
    SpawnTrackedTaskCallable,
    TaskRegistryProtocol,
)
from core.tasks.protocols_query import TaskRegistryQueryView
from orchestrator.internal_protocols import (
    OrchestratorActiveInferenceProtocol,
    OrchestratorCapacityProtocol,
    OrchestratorHandlersProtocol,
    OrchestratorInferenceExecutorProtocol,
    OrchestratorTaskOutcomesProtocol,
    TransientFailureCooldownsProtocol,
    VirtualModelHealthProtocol,
    VirtualModelRotationProtocol,
)
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.queueing.internal_protocols import QueueServiceView
from orchestrator.types import OrchestratorDependencies

__all__ = ("OrchestratorControlDependencies",)


@dataclass(frozen=True, slots=True)
class OrchestratorControlDependencies:
    orchestrator: OrchestratorDependencies
    config: OrchestratorRuntimeConfig
    queue: QueueServiceView
    scheduler: OrchestratorSchedulerProtocol
    inference_executor: OrchestratorInferenceExecutorProtocol
    outcomes: OrchestratorTaskOutcomesProtocol
    active_inferences: OrchestratorActiveInferenceProtocol
    handlers: OrchestratorHandlersProtocol
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    capacity: OrchestratorCapacityProtocol
    transient_failures: TransientFailureCooldownsProtocol
    virtual_model_health: VirtualModelHealthProtocol
    virtual_model_rotation: VirtualModelRotationProtocol
    task_registry: TaskRegistryProtocol
    task_registry_queries: TaskRegistryQueryView
    shutdown_event: asyncio.Event
    is_quiescent: asyncio.Event
    guardian_builder: Callable[[PluginGuardianDependencies], PluginGuardianProtocol]
    spawn_tracked_task: SpawnTrackedTaskCallable
    cancel_task: CancelTaskCallable

    def __post_init__(self) -> None:
        require_dependencies(
            owner="OrchestratorControlDependencies",
            active_inferences=self.active_inferences,
            cancel_task=self.cancel_task,
            capacity=self.capacity,
            config=self.config,
            guardian_builder=self.guardian_builder,
            handlers=self.handlers,
            inference_executor=self.inference_executor,
            is_quiescent=self.is_quiescent,
            lifecycle=self.lifecycle,
            orchestrator=self.orchestrator,
            outcomes=self.outcomes,
            queue=self.queue,
            scheduler=self.scheduler,
            shutdown_event=self.shutdown_event,
            spawn_tracked_task=self.spawn_tracked_task,
            task_registry=self.task_registry,
            task_registry_queries=self.task_registry_queries,
            transient_failures=self.transient_failures,
            virtual_model_health=self.virtual_model_health,
            virtual_model_rotation=self.virtual_model_rotation,
        )
