"""SoAI - Scheduler plugin guard checks [backend/orchestrator/scheduling/plugin_action_guards.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.state.state_names import ORCH_STATE_DISABLED
from core.state.state_transition_sets import (
    ALL_TRANSIENT_STATES,
    PLUGIN_MANAGER_TRANSIENT_STATES,
    SCHEDULER_DEFERRED_PLUGIN_STATES,
)
from orchestrator.scheduling.action_generation_dependencies import (
    SchedulerActionGenerationDependencies,
)
from orchestrator.scheduling.plugin_action_failure import (
    PluginActionFailure,
    build_prohibitive_state_failure,
)

__all__ = (
    "get_prohibitive_state_failure",
    "is_busy_or_transient",
)


async def get_prohibitive_state_failure(
    deps: SchedulerActionGenerationDependencies,
    plugin_name: str,
    plugin_status: str,
    pending_key: str,
) -> PluginActionFailure | None:
    if plugin_status == ORCH_STATE_DISABLED:
        failure = build_prohibitive_state_failure(plugin_name, plugin_status)
        await deps.queue.tracking.set_deferral_reason(pending_key, failure.operator_reason)
        return failure
    return None


async def is_busy_or_transient(
    deps: SchedulerActionGenerationDependencies,
    plugin_name: str,
    plugin_status: str,
    pending_key: str,
    state_is_busy: bool,
) -> bool:
    if (
        state_is_busy
        or plugin_status in ALL_TRANSIENT_STATES
        or plugin_status in SCHEDULER_DEFERRED_PLUGIN_STATES
        or plugin_status in PLUGIN_MANAGER_TRANSIENT_STATES
    ):
        await deps.queue.tracking.set_deferral_reason(
            pending_key,
            f"Plugin '{plugin_name}' is busy (state: {plugin_status}). Deferring action.",
        )
        return True
    return False
