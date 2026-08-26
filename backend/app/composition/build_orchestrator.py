"""SoAI - Orchestrator service dependency composition [backend/app/composition/build_orchestrator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from app.composition.build_orchestrator_control import (
    build_orchestrator_control_and_finalize,
)
from app.composition.build_orchestrator_core import build_orchestrator_core
from app.composition.build_orchestrator_execution import build_orchestrator_execution
from app.composition.orchestrator_service_components import (
    OrchestratorServiceComponents,
)
from core.tasks.protocols import (
    CancelTaskCallable,
    SpawnTrackedTaskCallable,
    TaskRegistryProtocol,
)
from core.tasks.protocols_query import TaskRegistryQueryView
from orchestrator.types import OrchestratorDependencies

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("build_orchestrator_services",)


def build_orchestrator_services(
    deps: OrchestratorDependencies,
    task_registry: TaskRegistryProtocol,
    task_registry_queries: TaskRegistryQueryView,
    *,
    tool_name_extractor: Callable[[list[JSONValue]], list[str]],
    spawn_tracked_task: SpawnTrackedTaskCallable,
    cancel_task: CancelTaskCallable,
    temp_directory: str | None = None,
) -> OrchestratorServiceComponents:
    core = build_orchestrator_core(
        deps=deps,
        task_registry=task_registry,
        tool_name_extractor=tool_name_extractor,
    )
    inference_executor, outcomes, active_inference_service = build_orchestrator_execution(
        deps=deps,
        config=core.config,
        queue=core.queue,
        lifecycle=core.lifecycle,
        capacity=core.capacity,
        transient_failures=core.transient_failures,
        virtual_model_health=core.virtual_model_health,
        task_registry=task_registry,
        temp_directory=temp_directory,
    )
    active_inferences = active_inference_service
    scheduler, handlers, control = build_orchestrator_control_and_finalize(
        deps=deps,
        config=core.config,
        queue=core.queue,
        lifecycle=core.lifecycle,
        transient_failures=core.transient_failures,
        virtual_model_health=core.virtual_model_health,
        virtual_model_rotation=core.virtual_model_rotation,
        capacity=core.capacity,
        task_registry=task_registry,
        task_registry_queries=task_registry_queries,
        shutdown_event=core.shutdown_event,
        is_quiescent=core.is_quiescent,
        inference_executor=inference_executor,
        outcomes=outcomes,
        active_inference_service=active_inferences,
        spawn_tracked_task=spawn_tracked_task,
        cancel_task=cancel_task,
    )
    return OrchestratorServiceComponents(
        control=control,
        scheduler=scheduler,
        queue=core.queue,
        lifecycle=core.lifecycle,
        handlers=handlers,
        inference_executor=inference_executor,
        outcomes=outcomes,
        active_inferences=active_inferences,
    )
