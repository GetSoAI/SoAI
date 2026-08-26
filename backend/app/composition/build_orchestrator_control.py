"""SoAI - Orchestrator control assembly helpers [backend/app/composition/build_orchestrator_control.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from app.composition.orchestrator_recovery_purge import (
    build_recovery_queue_purge_callback,
)
from core.errors.error_types import ErrorType
from core.orchestrator.runtime_config import OrchestratorRuntimeConfig
from core.tasks.protocols import (
    CancelTaskCallable,
    SpawnTrackedTaskCallable,
    TaskRegistryProtocol,
)
from core.tasks.protocols_query import TaskRegistryQueryView
from orchestrator.capacity.capacity_service import OrchestratorCapacity
from orchestrator.control.dependencies import OrchestratorControlDependencies
from orchestrator.control.plugin_queue_purge import (
    purge_plugin_requests_from_global_queues,
)
from orchestrator.control.plugin_queue_purge_dependencies import (
    PluginQueuePurgeDependencies,
)
from orchestrator.control.service import OrchestratorControl
from orchestrator.execution.active_inference_service import ActiveInferenceService
from orchestrator.execution.inference_executor import OrchestratorInferenceExecutor
from orchestrator.execution.outcomes import OutcomeManager
from orchestrator.failover_cooldowns import TransientFailureCooldowns
from orchestrator.handlers import OrchestratorHandlers, OrchestratorHandlersDependencies
from orchestrator.lifecycle.service import OrchestratorLifecycle
from orchestrator.queueing.service import OrchestratorQueue
from orchestrator.scheduling.dependencies import OrchestratorSchedulerDependencies
from orchestrator.scheduling.service import OrchestratorScheduler
from orchestrator.types import OrchestratorDependencies
from orchestrator.virtual_model_health import VirtualModelHealth
from orchestrator.virtual_model_rotation import VirtualModelRotation
from plugins.guardian.service import PluginGuardian

__all__ = ("build_orchestrator_control_and_finalize",)


def build_orchestrator_control_and_finalize(
    *,
    deps: OrchestratorDependencies,
    config: OrchestratorRuntimeConfig,
    queue: OrchestratorQueue,
    lifecycle: OrchestratorLifecycle,
    capacity: OrchestratorCapacity,
    transient_failures: TransientFailureCooldowns,
    virtual_model_health: VirtualModelHealth,
    virtual_model_rotation: VirtualModelRotation,
    task_registry: TaskRegistryProtocol,
    task_registry_queries: TaskRegistryQueryView,
    shutdown_event: asyncio.Event,
    is_quiescent: asyncio.Event,
    inference_executor: OrchestratorInferenceExecutor,
    outcomes: OutcomeManager,
    active_inference_service: ActiveInferenceService,
    spawn_tracked_task: SpawnTrackedTaskCallable,
    cancel_task: CancelTaskCallable,
) -> tuple[OrchestratorScheduler, OrchestratorHandlers, OrchestratorControl]:
    scheduler = OrchestratorScheduler(
        OrchestratorSchedulerDependencies(
            orchestrator=deps,
            config=config,
            routing_config=deps.routing_config,
            queue=queue,
            lifecycle=lifecycle,
            inference_executor=inference_executor,
            outcomes=outcomes,
            capacity=capacity,
            transient_failures=transient_failures,
            virtual_model_health=virtual_model_health,
            virtual_model_rotation=virtual_model_rotation,
            task_registry=task_registry,
            shutdown_event=shutdown_event,
        ),
    )
    handlers = OrchestratorHandlers(
        OrchestratorHandlersDependencies(
            queue=queue,
            is_quiescent=is_quiescent,
            task_registry=task_registry,
        ),
    )
    control = OrchestratorControl(
        OrchestratorControlDependencies(
            orchestrator=deps,
            config=config,
            queue=queue,
            scheduler=scheduler,
            inference_executor=inference_executor,
            outcomes=outcomes,
            active_inferences=active_inference_service,
            handlers=handlers,
            lifecycle=lifecycle,
            capacity=capacity,
            transient_failures=transient_failures,
            virtual_model_health=virtual_model_health,
            virtual_model_rotation=virtual_model_rotation,
            task_registry=task_registry,
            task_registry_queries=task_registry_queries,
            shutdown_event=shutdown_event,
            is_quiescent=is_quiescent,
            guardian_builder=PluginGuardian,
            spawn_tracked_task=spawn_tracked_task,
            cancel_task=cancel_task,
        ),
    )
    purge_deps = PluginQueuePurgeDependencies(
        orchestrator=deps,
        queue=queue,
        scheduler=scheduler,
        active_inferences=active_inference_service,
        outcomes=outcomes,
    )
    lifecycle.recovery.bind_queue_purge(build_recovery_queue_purge_callback(purge_deps))

    async def plugin_work_purge(
        *,
        plugin_name: str,
        purge_reason: str,
        fail_reason: str,
        error_type: ErrorType,
        operation: str,
    ) -> None:
        await purge_plugin_requests_from_global_queues(
            deps=purge_deps,
            plugin_name=plugin_name,
            purge_reason=purge_reason,
            fail_reason=fail_reason,
            error_type=error_type,
            operation=operation,
            allow_failover=False,
        )

    lifecycle.user_commands.bind_plugin_work_purge(plugin_work_purge)
    return (scheduler, handlers, control)
