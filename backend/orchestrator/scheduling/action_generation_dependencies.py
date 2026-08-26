"""SoAI - Scheduler action generation dependency types [backend/orchestrator/scheduling/action_generation_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.models.protocols import (
    ModelInformationServiceProtocol,
    ParameterManagerProtocol,
)
from core.orchestrator.execution_plan import ExecutionPlan
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.plugins.protocols import PluginManagerProtocol
from core.state.protocols import StateAggregatorProtocol
from core.tasks.protocols import TaskRegistryProtocol
from orchestrator.internal_protocols import OrchestratorCapacityProtocol
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)

if TYPE_CHECKING:
    from core.tasks.orchestration_context import OrchestrationContext
    from core.tasks.task import Task

    type ResolvePlanCallable = Callable[
        [Task, OrchestrationContext, set[str] | None],
        Awaitable[ExecutionPlan],
    ]
    type LifecycleLocksSnapshotCallable = Callable[[set[str]], dict[str, bool]]

__all__ = ("SchedulerActionGenerationDependencies",)


@dataclass(frozen=True, slots=True)
class SchedulerActionGenerationDependencies:
    queue: OrchestratorQueueProtocol
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    capacity: OrchestratorCapacityProtocol
    state_aggregator: StateAggregatorProtocol
    plugin_manager: PluginManagerProtocol
    model_information_service: ModelInformationServiceProtocol
    param_manager: ParameterManagerProtocol
    task_registry: TaskRegistryProtocol
    max_concurrent_plugins: int
    resolve_execution_plan: ResolvePlanCallable
    snapshot_outstanding_counts: Callable[[set[str]], Awaitable[dict[str, int]]]
    get_lifecycle_locks_snapshot: LifecycleLocksSnapshotCallable

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SchedulerActionGenerationDependencies",
            capacity=self.capacity,
            get_lifecycle_locks_snapshot=self.get_lifecycle_locks_snapshot,
            lifecycle=self.lifecycle,
            max_concurrent_plugins=self.max_concurrent_plugins,
            model_information_service=self.model_information_service,
            param_manager=self.param_manager,
            plugin_manager=self.plugin_manager,
            queue=self.queue,
            resolve_execution_plan=self.resolve_execution_plan,
            snapshot_outstanding_counts=self.snapshot_outstanding_counts,
            state_aggregator=self.state_aggregator,
            task_registry=self.task_registry,
        )
