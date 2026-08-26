"""SoAI - Scheduler action-generation data prefetch [backend/orchestrator/scheduling/scheduler_data_prefetch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.models.model_info_fields import coerce_plugin_name
from core.orchestrator.protocols_lifecycle import PluginStateProtocol
from core.orchestrator.routing_config import VirtualModelConfig
from core.state.state_transition_sets import SCHEDULER_INACTIVE_STATES
from orchestrator.scheduling.action_generation_dependencies import (
    SchedulerActionGenerationDependencies,
)
from orchestrator.scheduling.persistence_snapshot import (
    build_plugin_persistence_snapshot,
)

if TYPE_CHECKING:
    from core.state.protocols import ImmutablePluginStates
    from core.types.json import JSONDict

__all__ = (
    "SchedulerPrefetchData",
    "prefetch_scheduler_data",
)


@dataclass(frozen=True, slots=True)
class SchedulerPrefetchData:
    model_info_map: dict[str, JSONDict]
    plugin_params_map: dict[str, JSONDict]
    all_states: ImmutablePluginStates
    plugin_persistence: dict[str, bool]
    active_non_persistent_count: int
    lifecycle_locks: dict[str, bool]
    all_plugin_outstanding: dict[str, int]
    idle_plugins_snapshot: list[str]
    plugin_states_snapshot: dict[str, PluginStateProtocol]
    queue_empty_snapshot: dict[str, bool]
    pending_universal_ids_snapshot: dict[str, set[str]]
    virtual_model_map: dict[str, VirtualModelConfig]


async def prefetch_scheduler_data(
    deps: SchedulerActionGenerationDependencies,
    routing_keys_to_evaluate: set[str],
) -> SchedulerPrefetchData:
    virtual_model_map = await deps.lifecycle.startup.get_virtual_model_map()
    regular_universal_ids = [
        routing_key
        for routing_key in routing_keys_to_evaluate
        if routing_key not in virtual_model_map
    ]
    all_states = await deps.state_aggregator.get_all_plugin_states()
    model_info_map: dict[str, JSONDict] = {}
    plugin_params_map: dict[str, JSONDict] = {}
    if regular_universal_ids:
        model_info_map, plugin_params_map = await _fetch_model_and_plugin_params(
            deps,
            regular_universal_ids,
        )
    plugin_persistence, active_non_persistent_count = await build_plugin_persistence_snapshot(
        deps.plugin_manager,
        all_states,
        inactive_states=SCHEDULER_INACTIVE_STATES,
    )
    lifecycle_locks = deps.get_lifecycle_locks_snapshot(set(all_states.keys()))
    plugin_names_set = set(all_states.keys())
    plugin_names_list = list(plugin_names_set)
    (
        all_plugin_outstanding,
        idle_plugins_snapshot,
        plugin_states_snapshot,
        queue_empty_snapshot,
        pending_universal_ids_snapshot,
    ) = await asyncio.gather(
        deps.snapshot_outstanding_counts(plugin_names_set),
        deps.lifecycle.watchers.get_idle_plugins_snapshot(),
        deps.lifecycle.watchers.get_plugin_states_snapshot(plugin_names_set),
        deps.capacity.get_queue_empty_snapshot(plugin_names_list),
        deps.queue.tracking.get_pending_universal_ids_snapshot(),
        return_exceptions=False,
    )
    pending_universal_ids = {
        universal_id
        for universal_ids in pending_universal_ids_snapshot.values()
        for universal_id in universal_ids
    }
    missing_pending_universal_ids = list(pending_universal_ids - set(model_info_map))
    if missing_pending_universal_ids:
        extra_model_info, extra_plugin_params = await _fetch_model_and_plugin_params(
            deps,
            missing_pending_universal_ids,
        )
        model_info_map.update(extra_model_info)
        plugin_params_map.update(extra_plugin_params)
    return SchedulerPrefetchData(
        model_info_map=model_info_map,
        plugin_params_map=plugin_params_map,
        all_states=all_states,
        plugin_persistence=plugin_persistence,
        active_non_persistent_count=active_non_persistent_count,
        lifecycle_locks=lifecycle_locks,
        all_plugin_outstanding=all_plugin_outstanding,
        idle_plugins_snapshot=idle_plugins_snapshot,
        plugin_states_snapshot=plugin_states_snapshot,
        queue_empty_snapshot=queue_empty_snapshot,
        pending_universal_ids_snapshot=pending_universal_ids_snapshot,
        virtual_model_map=virtual_model_map,
    )


async def _fetch_model_and_plugin_params(
    deps: SchedulerActionGenerationDependencies,
    universal_ids: list[str],
) -> tuple[dict[str, JSONDict], dict[str, JSONDict]]:
    model_info_tasks = [
        deps.model_information_service.model_get_info(universal_id)
        for universal_id in universal_ids
    ]
    model_info_results = await asyncio.gather(*model_info_tasks, return_exceptions=False)
    model_info_map: dict[str, JSONDict] = {
        universal_id: info
        for universal_id, info in zip(universal_ids, model_info_results, strict=True)
        if info
    }
    plugin_params_map: dict[str, JSONDict] = {}
    if model_info_map:
        plugin_names = sorted(
            {
                plugin_name
                for info in model_info_map.values()
                if (plugin_name := coerce_plugin_name(info)) is not None
            },
        )
        if plugin_names:
            plugin_param_tasks = [
                deps.param_manager.get_all_parameters_for_plugin(name) for name in plugin_names
            ]
            plugin_params_results = await asyncio.gather(
                *plugin_param_tasks,
                return_exceptions=False,
            )
            plugin_params_map = {
                name: params
                for name, params in zip(plugin_names, plugin_params_results, strict=True)
                if params
            }
    return model_info_map, plugin_params_map
