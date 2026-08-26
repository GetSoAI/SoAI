"""SoAI - Scheduler action generation selection and execution [backend/orchestrator/scheduling/decisions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Collection, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.context import create_system_cancellation_id
from core.di.validation import require_dependencies
from core.logging.trace import get_logger
from core.orchestrator.protocols_queue import OrchestratorQueueProtocol
from core.orchestrator.routing_config import RoutingConfig
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY,
    SchedulerWorkItem,
)
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from orchestrator.internal_protocols import OrchestratorTaskOutcomesProtocol
from orchestrator.lifecycle.service_interfaces.internal_protocols import (
    OrchestratorLifecycleCoordinatorProtocol,
)
from orchestrator.lifecycle.start_task_tracking import scheduler_start_cancellation_id
from orchestrator.scheduling.action_generator import SchedulerActionGeneration
from orchestrator.scheduling.actions import SchedulerAction, SchedulerActionType
from orchestrator.scheduling.execution_selection import (
    SchedulerActionExecutionSelection,
    SchedulerActionExecutionSelectionDependencies,
)
from orchestrator.scheduling.internal_protocols import SchedulerCapacityProtocol
from orchestrator.scheduling.task_preparation import (
    SchedulerTaskPreparation,
    SchedulerTaskPreparationDependencies,
)
from orchestrator.scheduling.work_item_collection import collect_routing_keys

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from orchestrator.lifecycle.start_task_tracking import SchedulerStartTaskTracker

__all__ = (
    "SchedulerDecisionDependencies",
    "SchedulerDecisions",
)

LOGGER_NAME = "SoAI.orchestrator.scheduling.decisions"


@dataclass(frozen=True, slots=True)
class SchedulerDecisionDependencies:
    queue: OrchestratorQueueProtocol
    lifecycle: OrchestratorLifecycleCoordinatorProtocol
    outcomes: OrchestratorTaskOutcomesProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    queue_scheduler_work: Callable[[SchedulerWorkItem], Coroutine[None, None, None]]
    dispatch_waiters: Callable[[str, str, JSONDict], Awaitable[None]]
    action_generation: SchedulerActionGeneration
    capacity_service: SchedulerCapacityProtocol
    scheduler_start_task_tracker: SchedulerStartTaskTracker
    max_concurrent_plugins: int
    fair_dispatch_enabled: bool
    fair_dispatch_cap: int

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SchedulerDecisionDependencies",
            action_generation=self.action_generation,
            cancellation_binder=self.cancellation_binder,
            capacity_service=self.capacity_service,
            dispatch_waiters=self.dispatch_waiters,
            fair_dispatch_cap=self.fair_dispatch_cap,
            fair_dispatch_enabled=self.fair_dispatch_enabled,
            finalizer_tracker=self.finalizer_tracker,
            lifecycle=self.lifecycle,
            max_concurrent_plugins=self.max_concurrent_plugins,
            outcomes=self.outcomes,
            queue=self.queue,
            queue_scheduler_work=self.queue_scheduler_work,
            scheduler_start_task_tracker=self.scheduler_start_task_tracker,
        )


class SchedulerDecisions:
    def __init__(self, deps: SchedulerDecisionDependencies) -> None:
        self._deps = deps
        self._max_concurrent_plugins: int = deps.max_concurrent_plugins
        self._fair_dispatch_enabled: bool = deps.fair_dispatch_enabled
        self._fair_dispatch_cap: int = deps.fair_dispatch_cap
        self._scheduler_decision_lock = asyncio.Lock()
        self._task_preparation = SchedulerTaskPreparation(
            SchedulerTaskPreparationDependencies(
                lifecycle=self._deps.lifecycle,
                dispatch_waiters=self._deps.dispatch_waiters,
                fail_waiters=self._deps.outcomes.fail_waiters,
            ),
        )
        database_tasks = self._deps.queue.task_registry.database_tasks
        set_deferral_reason = self._deps.queue.tracking.set_deferral_reason
        routing_config: RoutingConfig = self._deps.queue.routing_config
        self._action_selection = SchedulerActionExecutionSelection(
            SchedulerActionExecutionSelectionDependencies(
                cancellation_binder=self._deps.cancellation_binder,
                finalizer_tracker=self._deps.finalizer_tracker,
                queue_scheduler_work=self._deps.queue_scheduler_work,
                capacity_service=self._deps.capacity_service,
                max_concurrent_plugins=self._max_concurrent_plugins,
                fair_dispatch_enabled=self._fair_dispatch_enabled,
                fair_dispatch_cap=self._fair_dispatch_cap,
                database_tasks=database_tasks,
                set_deferral_reason=set_deferral_reason,
                owner_running_limits_default=routing_config.owner_running_limits_default,
                owner_running_limits_by_owner_type=dict(
                    routing_config.owner_running_limits_by_owner_type,
                ),
            ),
        )

    def update_config(
        self,
        max_concurrent_plugins: int,
        fair_dispatch_enabled: bool,
        fair_dispatch_cap: int,
    ) -> None:
        self._max_concurrent_plugins = max_concurrent_plugins
        self._fair_dispatch_enabled = fair_dispatch_enabled
        self._fair_dispatch_cap = fair_dispatch_cap
        self._action_selection.update_config(
            max_concurrent_plugins,
            fair_dispatch_enabled,
            fair_dispatch_cap,
        )

    def update_routing_config(self, routing_config: RoutingConfig) -> None:
        self._action_selection.update_owner_running_limits(
            routing_config.owner_running_limits_default,
            dict(routing_config.owner_running_limits_by_owner_type),
        )

    def _spawn_action_task(self, action: SchedulerAction) -> asyncio.Task[None]:
        logger = get_logger(LOGGER_NAME)
        log_message, coro_factory = self._task_preparation.prepare(action)
        logger.debug("Scheduler decision (%s): %s", action.action_type.name, log_message)
        cancellation_id: str
        if action.action_type in (SchedulerActionType.START, SchedulerActionType.DISPATCH):
            if action.action_type == SchedulerActionType.START:
                cancellation_id = scheduler_start_cancellation_id(action.plugin_name)
            else:
                cancellation_id = create_system_cancellation_id(
                    f"scheduler_{action.action_type.name.lower()}_{action.plugin_name}",
                )
        else:
            cancellation_id = action.task.cancellation_id
        task = spawn_tracked_task(
            coro_factory(),
            name=f"orchestrator-scheduler-{action.action_type.name.lower()}-{action.task.task_id}",
            owner=f"scheduler_{action.action_type.name.lower()}",
            logger=logger,
            metadata={"plugin": action.plugin_name, "uid": action.universal_id},
            cancellation_id=cancellation_id,
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
        )
        if action.action_type == SchedulerActionType.START:
            self._deps.scheduler_start_task_tracker.track(action.plugin_name, task)
        return task

    async def evaluate_and_execute(self, work_items: Collection[SchedulerWorkItem]) -> None:
        logger = get_logger(LOGGER_NAME)
        routing_keys_to_evaluate = await collect_routing_keys(work_items, queue=self._deps.queue)
        if not routing_keys_to_evaluate:
            return
        prefetched_data = await self._deps.action_generation.prefetch_scheduler_data(
            routing_keys_to_evaluate,
        )
        async with self._scheduler_decision_lock:
            all_possible_actions, failures_to_process = (
                await self._deps.action_generation.generate_scheduler_actions(
                    routing_keys_to_evaluate,
                    prefetched_data,
                )
            )
            if not all_possible_actions and not failures_to_process:
                return
            actions_to_execute = (
                await self._action_selection.select_actions_to_execute(
                    all_possible_actions,
                    prefetched_data,
                )
                if all_possible_actions
                else []
            )
            if not actions_to_execute and not failures_to_process:
                return
            logger.trace(
                "Scheduler cycle decisions: %s actions to execute, %s failures to process.",
                len(actions_to_execute),
                len(failures_to_process),
            )
        dispatch_tasks: list[Awaitable[None]] = []
        for action in actions_to_execute:
            action_task = self._spawn_action_task(action)
            if action.action_type == SchedulerActionType.DISPATCH:
                dispatch_tasks.append(action_task)
        if dispatch_tasks:
            await asyncio.gather(*dispatch_tasks, return_exceptions=False)
        dispatch_keys = {
            action.pending_key or action.universal_id
            for action in actions_to_execute
            if action.action_type == SchedulerActionType.DISPATCH
        }
        if dispatch_keys:
            dispatch_tasks = [
                self._deps.queue_scheduler_work(
                    SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY, key),
                )
                for key in dispatch_keys
            ]
            await asyncio.gather(*dispatch_tasks, return_exceptions=False)
        if failures_to_process:
            fail_tasks = [
                self._deps.outcomes.fail_waiters(
                    key,
                    failure.message,
                    error_type=failure.error_type,
                )
                for key, failure in failures_to_process.items()
            ]
            await asyncio.gather(*fail_tasks, return_exceptions=False)
