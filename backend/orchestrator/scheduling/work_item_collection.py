"""SoAI - Scheduler work item and waiting plugin collection [backend/orchestrator/scheduling/work_item_collection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Collection, Container
from typing import TYPE_CHECKING

from core.models.provider_backing import is_provider_backed_model
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_ALL,
    SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN,
    SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY,
    SchedulerWorkItem,
)
from core.state.provider_backed_availability import (
    PROVIDER_BACKED_IGNORED_PLUGIN_STATES,
)
from core.state.state_transition_sets import SCHEDULER_INACTIVE_STATES
from orchestrator.scheduling.scheduler_data_prefetch import SchedulerPrefetchData

if TYPE_CHECKING:
    from core.orchestrator.protocols_queue import OrchestratorQueueProtocol

__all__ = (
    "collect_routing_keys",
    "identify_waiting_plugins",
)


async def collect_routing_keys(
    work_items: Collection[SchedulerWorkItem],
    *,
    queue: OrchestratorQueueProtocol,
) -> set[str]:
    routing_keys: set[str] = set()
    plugin_keys: set[str] = set()
    needs_all = False
    for item in work_items:
        if item.work_type == SCHEDULER_WORK_TYPE_EVALUATE_ROUTING_KEY:
            routing_keys.add(item.key)
        elif item.work_type == SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN:
            plugin_keys.add(item.key)
        elif item.work_type == SCHEDULER_WORK_TYPE_EVALUATE_ALL:
            needs_all = True
    if needs_all:
        routing_keys.update(await queue.tracking.get_pending_keys())
    if plugin_keys:
        routing_keys.update(await queue.tracking.get_pending_universal_ids_for_plugins(plugin_keys))
    return routing_keys


def identify_waiting_plugins(prefetched_data: SchedulerPrefetchData) -> set[str]:
    inactive_states = SCHEDULER_INACTIVE_STATES | {None}
    return {
        plugin_name
        for plugin_name, pending in prefetched_data.pending_universal_ids_snapshot.items()
        if pending
        and not prefetched_data.plugin_persistence.get(plugin_name)
        and _has_local_waiting_model(plugin_name, pending, prefetched_data, inactive_states)
    }


def _has_local_waiting_model(
    plugin_name: str,
    pending: set[str],
    prefetched_data: SchedulerPrefetchData,
    inactive_states: Container[str | None],
) -> bool:
    plugin_status_value = prefetched_data.all_states.get(plugin_name, {}).get("status")
    plugin_status = plugin_status_value if isinstance(plugin_status_value, str) else None
    if plugin_status not in inactive_states:
        return False
    for universal_id in pending:
        model_info = prefetched_data.model_info_map.get(universal_id)
        if (
            plugin_status in PROVIDER_BACKED_IGNORED_PLUGIN_STATES
            and model_info is not None
            and is_provider_backed_model(model_info)
        ):
            continue
        return True
    return False
