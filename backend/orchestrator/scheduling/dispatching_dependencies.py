"""SoAI - Scheduler dispatching dependency bundle [backend/orchestrator/scheduling/dispatching_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from core.models.protocols import ModelInformationServiceProtocol
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
    from core.plugins.protocols import PluginManagerProtocol
    from core.state.protocols import StateAggregatorProtocol
    from core.tasks.protocols import (
        CancellationHistoryProtocol,
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
    )
    from core.tasks.task import Task
    from orchestrator.internal_protocols import (
        OrchestratorCapacityProtocol,
        OrchestratorInferenceExecutorProtocol,
        OrchestratorTaskOutcomesProtocol,
    )
    from orchestrator.lifecycle.service_interfaces.internal_protocols import (
        OrchestratorLifecycleCoordinatorProtocol,
    )

__all__ = ("SchedulerDispatchingDependencies",)


@dataclass(frozen=True, slots=True)
class SchedulerDispatchingDependencies:
    queue: OrchestratorQueueProtocol
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    inference_executor: OrchestratorInferenceExecutorProtocol
    outcomes: OrchestratorTaskOutcomesProtocol
    capacity: OrchestratorCapacityProtocol
    cancellation_history: CancellationHistoryProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    task_registry: TaskRegistryProtocol
    state_aggregator: StateAggregatorProtocol
    plugin_manager: PluginManagerProtocol
    model_information_service: ModelInformationServiceProtocol
    shutdown_event: asyncio.Event
    dispatch_ready_states: set[str]
    ensure_plugin_capacity: Callable[[str], Awaitable[None]]
    schedule_plugin_dispatch: Callable[[Task, str], Awaitable[None]]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SchedulerDispatchingDependencies",
            cancellation_binder=self.cancellation_binder,
            cancellation_history=self.cancellation_history,
            capacity=self.capacity,
            dispatch_ready_states=self.dispatch_ready_states,
            ensure_plugin_capacity=self.ensure_plugin_capacity,
            finalizer_tracker=self.finalizer_tracker,
            inference_executor=self.inference_executor,
            lifecycle=self.lifecycle,
            model_information_service=self.model_information_service,
            outcomes=self.outcomes,
            plugin_manager=self.plugin_manager,
            queue=self.queue,
            schedule_plugin_dispatch=self.schedule_plugin_dispatch,
            shutdown_event=self.shutdown_event,
            state_aggregator=self.state_aggregator,
            task_registry=self.task_registry,
        )
