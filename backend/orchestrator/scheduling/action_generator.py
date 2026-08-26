"""SoAI - Scheduler action generation coordinator [backend/orchestrator/scheduling/action_generator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.error_types import ErrorType
from core.logging.trace import get_logger
from core.models.model_info_fields import coerce_plugin_name
from core.orchestrator.routing_config import VirtualModelConfig
from core.tasks.enums import TaskStatus
from orchestrator.queueing.deferred_task_context_repair import (
    try_repair_deferred_task_context,
)
from orchestrator.scheduling.action_generation_dependencies import (
    SchedulerActionGenerationDependencies,
)
from orchestrator.scheduling.actions import SchedulerAction
from orchestrator.scheduling.plugin_action_determination import (
    PluginActionEvaluation,
    determine_plugin_action,
)
from orchestrator.scheduling.plugin_action_failure import PluginActionFailure
from orchestrator.scheduling.scheduler_data_prefetch import (
    SchedulerPrefetchData,
    prefetch_scheduler_data,
)
from orchestrator.scheduling.virtual_model_evaluation import (
    evaluate_virtual_model_routing,
)

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginStates
    from core.types.json import JSONDict

__all__ = ("SchedulerActionGeneration",)

LOGGER_NAME = "SoAI.orchestrator.scheduling.action_generator"


class SchedulerActionGeneration:
    def __init__(self, deps: SchedulerActionGenerationDependencies) -> None:
        self._deps = deps
        self._max_concurrent_plugins: int = deps.max_concurrent_plugins

    def update_config(self, max_concurrent_plugins: int) -> None:
        self._max_concurrent_plugins = max_concurrent_plugins

    async def prefetch_scheduler_data(
        self,
        routing_keys_to_evaluate: set[str],
    ) -> SchedulerPrefetchData:
        return await prefetch_scheduler_data(self._deps, routing_keys_to_evaluate)

    async def generate_scheduler_actions(
        self,
        routing_keys_to_evaluate: set[str],
        prefetched_data: SchedulerPrefetchData,
    ) -> tuple[list[SchedulerAction], dict[str, PluginActionFailure]]:
        all_states = prefetched_data.all_states
        plugin_persistence = prefetched_data.plugin_persistence
        lifecycle_locks = prefetched_data.lifecycle_locks
        model_info_map = prefetched_data.model_info_map
        virtual_model_map = prefetched_data.virtual_model_map
        actions: list[SchedulerAction] = []
        failures_to_process: dict[str, PluginActionFailure] = {}
        for key in routing_keys_to_evaluate:
            if key in failures_to_process:
                continue
            result = await self._evaluate_single_routing_key(
                key,
                virtual_model_map,
                model_info_map,
                lifecycle_locks,
                all_states,
                plugin_persistence,
                prefetched_data,
            )
            if result.action:
                actions.append(result.action)
            if result.failure is not None:
                failures_to_process[result.pending_key] = result.failure
        return (actions, failures_to_process)

    async def _evaluate_single_routing_key(
        self,
        key: str,
        virtual_model_map: dict[str, VirtualModelConfig],
        model_info_map: dict[str, JSONDict],
        lifecycle_locks: dict[str, bool],
        all_states: ImmutablePluginStates,
        plugin_persistence: dict[str, bool],
        prefetched_data: SchedulerPrefetchData,
    ) -> _EvaluationResult:
        task, _, task_status = await self._deps.queue.tracking.peek_pending_task(key)
        if not task:
            return _EvaluationResult(pending_key=key)
        if task_status == TaskStatus.CANCELLED:
            return _EvaluationResult(
                pending_key=key,
                failure=_make_server_failure("Task cancelled while pending."),
            )
        context = self._deps.queue.require_orchestration_context(task)
        if context.event is None:
            return _EvaluationResult(
                pending_key=key,
                failure=_make_server_failure("Task missing inference event."),
            )
        vm_result = await evaluate_virtual_model_routing(
            self._deps,
            task,
            context,
            key,
            virtual_model_map,
        )
        if vm_result.status == "on_cooldown":
            return _EvaluationResult(pending_key=key)
        if vm_result.status == "unavailable":
            vm_failure = (
                _make_server_failure(vm_result.failure_reason)
                if vm_result.failure_reason is not None
                else None
            )
            return _EvaluationResult(pending_key=key, failure=vm_failure)
        task = vm_result.task
        context = vm_result.context
        pending_key = vm_result.pending_key
        universal_id = vm_result.universal_id
        if not universal_id:
            return _EvaluationResult(pending_key=pending_key)
        model_info = (
            vm_result.model_info
            if vm_result.model_info is not None
            else model_info_map.get(universal_id)
        )
        if not model_info:
            return _EvaluationResult(
                pending_key=pending_key,
                failure=_make_server_failure(f"Model {universal_id} not found."),
            )
        plugin_name = (
            vm_result.plugin_name
            if vm_result.plugin_name is not None
            else coerce_plugin_name(model_info)
        )
        if plugin_name is None:
            return _EvaluationResult(
                pending_key=pending_key,
                failure=_make_server_failure(f"Model {universal_id} missing plugin field."),
            )
        if not context.execution_universal_ids and key not in virtual_model_map:
            logger = get_logger(LOGGER_NAME)
            logger.warning(
                "Repairing task [%s] missing execution plan for routing key '%s' (model=%s, plugin=%s).",
                task.task_id,
                key,
                universal_id,
                plugin_name,
            )
            repair_result = await try_repair_deferred_task_context(
                self._deps.queue,
                task,
                context,
                deferral_key=universal_id,
                logger=logger,
                operation="orchestrator.queue.defer.persist_repair_context",
                expected_plugin_name=plugin_name,
            )
            if not repair_result.plugin_matches:
                await self._deps.queue.tracking.set_deferral_reason(
                    pending_key,
                    "Task execution plan repair failed (model plugin mismatch).",
                )
                return _EvaluationResult(pending_key=pending_key)
            if not repair_result.persisted:
                await self._deps.queue.tracking.set_deferral_reason(
                    pending_key,
                    "Task execution plan repair failed (could not persist orchestration state).",
                )
                return _EvaluationResult(pending_key=pending_key)
            task = repair_result.task
            context = repair_result.context
        if key in virtual_model_map and vm_result.moved:
            await self._deps.queue.tracking.add_pending_universal_id_for_plugin(
                plugin_name,
                universal_id,
            )
        if lifecycle_locks.get(plugin_name, False):
            await self._deps.queue.tracking.set_deferral_reason(
                pending_key,
                f"Plugin '{plugin_name}' is locked for a lifecycle operation.",
            )
            return _EvaluationResult(pending_key=pending_key)
        action_result = await determine_plugin_action(
            self._deps,
            PluginActionEvaluation(
                task=task,
                context=context,
                universal_id=universal_id,
                plugin_name=plugin_name,
                model_info=model_info,
                pending_key=pending_key,
                all_states=all_states,
                plugin_persistence=plugin_persistence,
                prefetched_data=prefetched_data,
                max_concurrent_plugins=self._max_concurrent_plugins,
            ),
        )
        return _EvaluationResult(
            pending_key=pending_key,
            action=action_result.action,
            failure=action_result.failure,
        )


def _make_server_failure(message: str) -> PluginActionFailure:
    return PluginActionFailure(
        message=message,
        operator_reason=message,
        error_type=ErrorType.SERVER_ERROR,
    )


class _EvaluationResult:
    __slots__ = ("action", "failure", "pending_key")

    def __init__(
        self,
        pending_key: str,
        action: SchedulerAction | None = None,
        failure: PluginActionFailure | None = None,
    ) -> None:
        self.pending_key = pending_key
        self.action = action
        self.failure = failure
