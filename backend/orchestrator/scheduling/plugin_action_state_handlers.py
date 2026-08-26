"""SoAI - Scheduler plugin action state handlers [backend/orchestrator/scheduling/plugin_action_state_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from orchestrator.scheduling.action_construction import (
    SchedulerActionInputs,
    build_dispatch_action,
    build_evict_and_start_action,
    build_reload_action,
    build_start_action,
)
from orchestrator.scheduling.plugin_action_failure import PluginActionFailure

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginStates
    from core.tasks.orchestration_context import OrchestrationContext
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from orchestrator.scheduling.action_generation_dependencies import (
        SchedulerActionGenerationDependencies,
    )
    from orchestrator.scheduling.actions import SchedulerAction
    from orchestrator.scheduling.scheduler_data_prefetch import SchedulerPrefetchData

__all__ = (
    "PluginActionResult",
    "handle_ready_plugin",
    "handle_stopped_plugin",
)


@dataclass(frozen=True, slots=True)
class PluginActionResult:
    outcome: Literal["action", "deferred", "failed"]
    action: SchedulerAction | None = None
    failure: PluginActionFailure | None = None


async def handle_stopped_plugin(
    deps: SchedulerActionGenerationDependencies,
    task: Task,
    context: OrchestrationContext,
    universal_id: str,
    plugin_name: str,
    model_info: JSONDict,
    pending_key: str,
    all_states: ImmutablePluginStates,
    plugin_persistence: dict[str, bool],
    prefetched_data: SchedulerPrefetchData,
    max_concurrent_plugins: int,
    active_non_persistent_count: int,
) -> PluginActionResult:
    action_inputs = SchedulerActionInputs(
        priority_order=context.priority_assignment.priority_order,
        universal_id=universal_id,
        plugin_name=plugin_name,
        task=task,
        model_info=model_info,
        pending_key=pending_key,
    )
    if (
        plugin_persistence.get(plugin_name)
        or max_concurrent_plugins <= 0
        or active_non_persistent_count < max_concurrent_plugins
    ):
        return PluginActionResult(
            outcome="action",
            action=build_start_action(action_inputs),
        )
    victim = await deps.lifecycle.task_tracking.find_eviction_candidate(
        plugin_persistence,
        exclude={plugin_name},
        all_states=all_states,
        idle_plugins_snapshot=prefetched_data.idle_plugins_snapshot,
        plugin_states_snapshot=prefetched_data.plugin_states_snapshot,
        queue_empty_snapshot=prefetched_data.queue_empty_snapshot,
    )
    if victim:
        return PluginActionResult(
            outcome="action",
            action=build_evict_and_start_action(action_inputs, victim_plugin=victim),
        )
    await deps.queue.tracking.set_deferral_reason(
        pending_key,
        f"At capacity ({max_concurrent_plugins}), but no eviction candidate found.",
    )
    return PluginActionResult(outcome="deferred")


async def handle_ready_plugin(
    deps: SchedulerActionGenerationDependencies,
    task: Task,
    context: OrchestrationContext,
    universal_id: str,
    plugin_name: str,
    model_info: JSONDict,
    pending_key: str,
    state_loaded_model_universal_id: str | None,
    state_loaded_parameters: JSONDict | None,
    request_params: JSONDict,
) -> PluginActionResult:
    action_inputs = SchedulerActionInputs(
        priority_order=context.priority_assignment.priority_order,
        universal_id=universal_id,
        plugin_name=plugin_name,
        task=task,
        model_info=model_info,
        pending_key=pending_key,
    )
    params_match = await deps.lifecycle.task_tracking.reload_params_match(
        plugin_name,
        state_loaded_parameters,
        request_params,
    )
    if state_loaded_model_universal_id != universal_id or (not params_match):
        return PluginActionResult(
            outcome="action",
            action=build_reload_action(action_inputs),
        )
    await deps.queue.tracking.set_deferral_reason(
        pending_key,
        f"Model '{universal_id}' is ready; dispatching from scheduler.",
    )
    return PluginActionResult(
        outcome="action",
        action=build_dispatch_action(action_inputs),
    )
