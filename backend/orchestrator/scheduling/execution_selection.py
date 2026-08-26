"""SoAI - Scheduler action execution selection and follow-up scheduling [backend/orchestrator/scheduling/execution_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Coroutine, Sequence
from dataclasses import dataclass

from core.database.protocols_tasks import DatabaseTasksProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_ALL,
    SchedulerWorkItem,
)
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tasks.task_cancellation_ops import generate_system_cancellation_id
from core.tasks.type_catalog import is_orchestrated_inference_task_type
from orchestrator.scheduling.actions import SchedulerAction, SchedulerActionType
from orchestrator.scheduling.fairness_limits import compute_fairness_limit
from orchestrator.scheduling.internal_protocols import SchedulerCapacityProtocol
from orchestrator.scheduling.scheduler_data_prefetch import SchedulerPrefetchData
from orchestrator.scheduling.work_item_collection import identify_waiting_plugins

__all__ = (
    "SchedulerActionExecutionSelection",
    "SchedulerActionExecutionSelectionDependencies",
)

LOGGER_NAME = "SoAI.orchestrator.scheduling.execution_selection"
OPERATION = "orchestrator.scheduling.decisions.run_scheduler_cycle"


@dataclass(frozen=True, slots=True)
class SchedulerActionExecutionSelectionDependencies:
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    queue_scheduler_work: Callable[[SchedulerWorkItem], Coroutine[None, None, None]]
    capacity_service: SchedulerCapacityProtocol
    max_concurrent_plugins: int
    fair_dispatch_enabled: bool
    fair_dispatch_cap: int
    database_tasks: DatabaseTasksProtocol | None
    set_deferral_reason: Callable[[str | None, str], Coroutine[None, None, None]] | None
    owner_running_limits_default: int
    owner_running_limits_by_owner_type: dict[str, int]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="SchedulerActionExecutionSelectionDependencies",
            cancellation_binder=self.cancellation_binder,
            capacity_service=self.capacity_service,
            fair_dispatch_cap=self.fair_dispatch_cap,
            fair_dispatch_enabled=self.fair_dispatch_enabled,
            finalizer_tracker=self.finalizer_tracker,
            max_concurrent_plugins=self.max_concurrent_plugins,
            owner_running_limits_by_owner_type=self.owner_running_limits_by_owner_type,
            owner_running_limits_default=self.owner_running_limits_default,
            queue_scheduler_work=self.queue_scheduler_work,
        )


class SchedulerActionExecutionSelection:
    def __init__(self, deps: SchedulerActionExecutionSelectionDependencies) -> None:
        self._deps = deps
        self._max_concurrent_plugins = deps.max_concurrent_plugins
        self._fair_dispatch_enabled = deps.fair_dispatch_enabled
        self._fair_dispatch_cap = deps.fair_dispatch_cap
        self._owner_running_limits_default = deps.owner_running_limits_default
        self._owner_running_limits_by_owner_type = deps.owner_running_limits_by_owner_type

    def update_config(
        self,
        max_concurrent_plugins: int,
        fair_dispatch_enabled: bool,
        fair_dispatch_cap: int,
    ) -> None:
        self._max_concurrent_plugins = max_concurrent_plugins
        self._fair_dispatch_enabled = fair_dispatch_enabled
        self._fair_dispatch_cap = fair_dispatch_cap

    def update_owner_running_limits(
        self,
        owner_running_limits_default: int,
        owner_running_limits_by_owner_type: dict[str, int],
    ) -> None:
        self._owner_running_limits_default = owner_running_limits_default
        self._owner_running_limits_by_owner_type = owner_running_limits_by_owner_type

    async def select_actions_to_execute(
        self,
        all_actions: Sequence[SchedulerAction],
        prefetched_data: SchedulerPrefetchData,
    ) -> list[SchedulerAction]:
        logger = get_logger(LOGGER_NAME)
        waiting_plugins = identify_waiting_plugins(prefetched_data)
        fairness_active = (
            self._fair_dispatch_enabled
            and self._fair_dispatch_cap > 0
            and waiting_plugins
            and self._max_concurrent_plugins > 0
            and prefetched_data.active_non_persistent_count >= self._max_concurrent_plugins
        )
        dispatch_actions: list[SchedulerAction] = []
        heavy_actions: list[SchedulerAction] = []
        for action in all_actions:
            if action.action_type == SchedulerActionType.DISPATCH:
                dispatch_actions.append(action)
            else:
                heavy_actions.append(action)
        dispatch_actions.sort(key=lambda action: (action.priority_order, action.task.task_id))
        heavy_actions.sort(key=lambda action: (action.priority_order, action.task.task_id))
        committed_plugins: set[str] = set()
        dispatched_universal_ids: set[str] = set()
        actions_to_execute: list[SchedulerAction] = []
        plugins_with_dispatch: set[str] = set()
        dispatch_counts: dict[str, int] = {}
        owner_selected_counts: dict[tuple[str, str], int] = {}
        owner_running_counts: dict[tuple[str, str], int] = {}
        needs_followup = False
        database_tasks = self._deps.database_tasks
        owner_limit_default = self._owner_running_limits_default
        owner_limits_by_type = self._owner_running_limits_by_owner_type
        set_deferral_reason = self._deps.set_deferral_reason
        for action in dispatch_actions:
            if action.universal_id in dispatched_universal_ids:
                needs_followup = True
                continue
            if (
                fairness_active
                and (not prefetched_data.plugin_persistence.get(action.plugin_name))
                and action.plugin_name not in waiting_plugins
            ):
                outstanding = prefetched_data.all_plugin_outstanding.get(
                    action.plugin_name,
                    0,
                ) + dispatch_counts.get(action.plugin_name, 0)
                if outstanding >= self._compute_fairness_limit(action.plugin_name):
                    logger.trace(
                        "Fair-dispatch throttle: skipping dispatch of universal id '%s' on '%s' while plugins %s await capacity.",
                        action.universal_id,
                        action.plugin_name,
                        sorted(waiting_plugins),
                    )
                    needs_followup = True
                    continue
            if database_tasks is not None and is_orchestrated_inference_task_type(
                action.task.task_type
            ):
                owner_type = action.task.owner_type
                owner_id = action.task.owner_id
                owner_limit = owner_limits_by_type.get(owner_type, owner_limit_default)
                if owner_limit > 0:
                    owner_key = (owner_type, owner_id)
                    running_count = owner_running_counts.get(owner_key)
                    if running_count is None:
                        running_count = await database_tasks.count_running_orchestrated_inference_tasks_for_owner(
                            owner_type,
                            owner_id,
                        )
                        owner_running_counts[owner_key] = running_count
                    selected_count = owner_selected_counts.get(owner_key, 0)
                    if running_count + selected_count >= owner_limit:
                        if set_deferral_reason is not None:
                            await set_deferral_reason(
                                action.pending_key,
                                f"Owner running limit reached for {owner_type}:{owner_id} ({running_count + selected_count}/{owner_limit}).",
                            )
                        needs_followup = True
                        continue
                    owner_selected_counts[owner_key] = selected_count + 1
            actions_to_execute.append(action)
            plugins_with_dispatch.add(action.plugin_name)
            dispatched_universal_ids.add(action.universal_id)
            dispatch_counts[action.plugin_name] = dispatch_counts.get(action.plugin_name, 0) + 1
        available_slots: int | None = (
            None
            if self._max_concurrent_plugins <= 0
            else max(self._max_concurrent_plugins - prefetched_data.active_non_persistent_count, 0)
        )
        for action in heavy_actions:
            plugin = action.plugin_name
            victim = action.victim_plugin
            if plugin in committed_plugins or plugin in plugins_with_dispatch:
                continue
            if victim and (victim in committed_plugins or victim in plugins_with_dispatch):
                continue
            action_type = action.action_type
            if action_type == SchedulerActionType.RELOAD:
                actions_to_execute.append(action)
                committed_plugins.add(plugin)
            elif action_type == SchedulerActionType.START:
                is_persistent_plugin = bool(prefetched_data.plugin_persistence.get(plugin))
                if is_persistent_plugin or available_slots is None or available_slots > 0:
                    actions_to_execute.append(action)
                    committed_plugins.add(plugin)
                    if available_slots is not None and not is_persistent_plugin:
                        available_slots -= 1
                else:
                    needs_followup = True
            elif action_type == SchedulerActionType.EVICT_AND_START and victim:
                actions_to_execute.append(action)
                committed_plugins.add(plugin)
                committed_plugins.add(victim)
                needs_followup = True
        if (fairness_active and actions_to_execute and waiting_plugins) or needs_followup:
            self._schedule_followup()
        return actions_to_execute

    def _compute_fairness_limit(self, plugin_name: str) -> int:
        configured = self._deps.capacity_service.resolve_plugin_limit_for_fairness(plugin_name)
        return compute_fairness_limit(
            configured_limit=configured,
            fair_dispatch_cap=self._fair_dispatch_cap,
        )

    def _schedule_followup(self) -> None:
        logger = get_logger(LOGGER_NAME)
        try:
            _ = spawn_tracked_task(
                self._deps.queue_scheduler_work(
                    SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_ALL, "fairness_followup"),
                ),
                name="scheduler-fairness-followup",
                owner="scheduler_fairness_followup",
                logger=logger,
                cancellation_binder=self._deps.cancellation_binder,
                finalizer_tracker=self._deps.finalizer_tracker,
                cancellation_id=generate_system_cancellation_id("scheduler_fairness_followup"),
            )
        except RuntimeError as exception:
            log_exception(
                logger,
                exception,
                message="Failed to schedule fairness follow-up",
                operation=OPERATION,
                level="warning",
            )
