"""SoAI - Scheduler action determination from plugin state [backend/orchestrator/scheduling/plugin_action_determination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.models.provider_backing import is_provider_backed_model
from core.state.state_names import (
    ORCH_STATE_READY,
    ORCH_STATE_READY_DIRTY,
    ORCH_STATE_STOPPED,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_STOPPED,
)
from core.state.state_transition_sets import DISPATCH_READY_STATES
from core.tasks.orchestration_context import OrchestrationContext
from core.tasks.task import Task
from orchestrator.scheduling.action_construction import (
    SchedulerActionInputs,
    build_dispatch_action,
)
from orchestrator.scheduling.action_generation_dependencies import (
    SchedulerActionGenerationDependencies,
)
from orchestrator.scheduling.plugin_action_guards import (
    get_prohibitive_state_failure,
    is_busy_or_transient,
)
from orchestrator.scheduling.plugin_action_state_handlers import (
    PluginActionResult,
    handle_ready_plugin,
    handle_stopped_plugin,
)
from orchestrator.scheduling.provider_backed_readiness import (
    get_provider_aware_ready_states,
)
from orchestrator.scheduling.scheduler_data_prefetch import SchedulerPrefetchData

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginStates
    from core.types.json import JSONDict

__all__ = (
    "PluginActionEvaluation",
    "determine_plugin_action",
)


@dataclass(frozen=True, slots=True)
class PluginActionEvaluation:
    task: Task
    context: OrchestrationContext
    universal_id: str
    plugin_name: str
    model_info: JSONDict
    pending_key: str
    all_states: ImmutablePluginStates
    plugin_persistence: dict[str, bool]
    prefetched_data: SchedulerPrefetchData
    max_concurrent_plugins: int


async def determine_plugin_action(
    deps: SchedulerActionGenerationDependencies,
    evaluation: PluginActionEvaluation,
) -> PluginActionResult:
    state = await deps.lifecycle.watchers.get_plugin_state(evaluation.plugin_name)
    state_loaded_model_universal_id: str | None = None
    state_loaded_parameters: JSONDict | None = None
    state_is_busy = False
    if state is not None:
        state_loaded_model_universal_id = state.loaded_model_universal_id
        state_loaded_parameters = state.loaded_parameters
        state_is_busy = bool(state.is_busy)
    plugin_status_value = evaluation.all_states.get(evaluation.plugin_name, {}).get("status")
    plugin_status = (
        plugin_status_value if isinstance(plugin_status_value, str) else PLUGIN_STATE_NOT_DETECTED
    )
    action_inputs = SchedulerActionInputs(
        priority_order=evaluation.context.priority_assignment.priority_order,
        universal_id=evaluation.universal_id,
        plugin_name=evaluation.plugin_name,
        task=evaluation.task,
        model_info=evaluation.model_info,
        pending_key=evaluation.pending_key,
    )
    request_params = dict(evaluation.context.startup_params)
    provider_backed = is_provider_backed_model(evaluation.model_info)
    ready_result = await _check_model_readiness(
        deps,
        action_inputs,
        plugin_status,
        evaluation.plugin_persistence,
        state_loaded_model_universal_id,
        state_loaded_parameters,
        request_params,
        provider_backed,
    )
    if ready_result is not None:
        return ready_result
    failure = await get_prohibitive_state_failure(
        deps,
        evaluation.plugin_name,
        plugin_status,
        evaluation.pending_key,
    )
    if failure is not None:
        return PluginActionResult(outcome="failed", failure=failure)
    if await is_busy_or_transient(
        deps,
        evaluation.plugin_name,
        plugin_status,
        evaluation.pending_key,
        state_is_busy,
    ):
        return PluginActionResult(outcome="deferred")
    return await _determine_action_for_state(
        deps,
        evaluation,
        plugin_status,
        state_loaded_model_universal_id,
        state_loaded_parameters,
        request_params,
    )


async def _check_model_readiness(
    deps: SchedulerActionGenerationDependencies,
    action_inputs: SchedulerActionInputs,
    plugin_status: str,
    plugin_persistence: dict[str, bool],
    state_loaded_model_universal_id: str | None,
    state_loaded_parameters: JSONDict | None,
    request_params: JSONDict,
    provider_backed: bool,
) -> PluginActionResult | None:
    ready_states = get_provider_aware_ready_states(set(DISPATCH_READY_STATES), provider_backed)
    if plugin_status not in ready_states:
        return None
    if provider_backed:
        return PluginActionResult(
            outcome="action",
            action=build_dispatch_action(action_inputs),
        )
    is_persistent = plugin_persistence.get(action_inputs.plugin_name, False)
    if is_persistent:
        return PluginActionResult(
            outcome="action",
            action=build_dispatch_action(action_inputs),
        )
    if state_loaded_model_universal_id == action_inputs.universal_id:
        params_match = await deps.lifecycle.task_tracking.reload_params_match(
            action_inputs.plugin_name,
            state_loaded_parameters,
            request_params,
        )
        if params_match:
            return PluginActionResult(
                outcome="action",
                action=build_dispatch_action(action_inputs),
            )
    return None


async def _determine_action_for_state(
    deps: SchedulerActionGenerationDependencies,
    evaluation: PluginActionEvaluation,
    plugin_status: str,
    state_loaded_model_universal_id: str | None,
    state_loaded_parameters: JSONDict | None,
    request_params: JSONDict,
) -> PluginActionResult:
    active_non_persistent_count = evaluation.prefetched_data.active_non_persistent_count
    if plugin_status in {ORCH_STATE_STOPPED, PLUGIN_STATE_STOPPED}:
        return await handle_stopped_plugin(
            deps,
            evaluation.task,
            evaluation.context,
            evaluation.universal_id,
            evaluation.plugin_name,
            evaluation.model_info,
            evaluation.pending_key,
            evaluation.all_states,
            evaluation.plugin_persistence,
            evaluation.prefetched_data,
            evaluation.max_concurrent_plugins,
            active_non_persistent_count,
        )
    if plugin_status in {ORCH_STATE_READY, ORCH_STATE_READY_DIRTY}:
        return await handle_ready_plugin(
            deps,
            evaluation.task,
            evaluation.context,
            evaluation.universal_id,
            evaluation.plugin_name,
            evaluation.model_info,
            evaluation.pending_key,
            state_loaded_model_universal_id,
            state_loaded_parameters,
            request_params,
        )
    return PluginActionResult(outcome="deferred")
