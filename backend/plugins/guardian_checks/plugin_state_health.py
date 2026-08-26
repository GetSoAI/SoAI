"""SoAI - Guardian plugin state health checks [backend/plugins/guardian_checks/plugin_state_health.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

from core.errors.exception_logging import log_exception
from core.logging.trace import get_logger
from core.metrics.keyspace_base import DIRECTOR_GAUGE_PLUGIN_HEALTH
from core.state.circuit_breaker import CircuitBreakerState
from core.state.state_names import (
    ORCH_STATE_DISABLED,
    ORCH_STATE_ERROR,
    ORCH_STATE_LOADING,
    ORCH_STATE_QUARANTINED,
    ORCH_STATE_STARTING,
    PLUGIN_STATE_BACKEND_INSTALLING,
)
from core.state.state_transition_sets import ALL_TRANSIENT_STATES
from plugins.guardian.candidates import collect_unlocked_guardian_plugin_names
from plugins.guardian.eligibility import (
    GUARDIAN_LOGGER_NAME,
    is_plugin_state_health_candidate,
)
from plugins.guardian.state_snapshot import (
    get_last_updated_monotonic,
    get_plugin_status,
)
from plugins.guardian_flapping import collect_recent_state_transitions, is_flapping
from plugins.protocols_internal.guardian.internal_protocols import (
    PluginGuardianInternalProtocol,
)

if TYPE_CHECKING:
    from plugins.guardian.check_context import GuardianCheckContext

__all__ = (
    "check_plugin_states",
    "update_health_metrics",
)

GUARDIAN_HEALTH_METRIC_CONCURRENCY: int = 8
OPERATION_PLUGIN_GUARDIAN_UPDATE_HEALTH_METRICS = "plugin_guardian.update_health_metrics"


async def check_plugin_states(
    self: PluginGuardianInternalProtocol,
    *,
    check_context: GuardianCheckContext,
    now_monotonic: float,
    stuck_state_timeout: float,
    flapping_window: float,
    flapping_min_transitions: int,
) -> dict[str, str]:
    plugins_to_recover: dict[str, str] = {}
    for plugin_name, plugin_state_info in check_context.plugin_states.items():
        current_status = plugin_state_info.status
        if not is_plugin_state_health_candidate(check_context, plugin_name, current_status):
            continue
        effective_timeout = (
            stuck_state_timeout * 3
            if current_status
            in {ORCH_STATE_LOADING, ORCH_STATE_STARTING, PLUGIN_STATE_BACKEND_INSTALLING}
            else stuck_state_timeout
        )
        reason: str | None = None
        if current_status == ORCH_STATE_ERROR:
            reason = "plugin found in persistent ERROR state during health check."
        elif current_status in ALL_TRANSIENT_STATES:
            last_updated_monotonic = get_last_updated_monotonic(
                check_context.plugin_states,
                plugin_name,
                default=now_monotonic,
            )
            if now_monotonic - last_updated_monotonic > effective_timeout:
                reason = (
                    f"stuck in transient state '{current_status}' for over {effective_timeout:.0f}s"
                )
        state_history = self.state_history.get(plugin_name)
        if state_history is not None and is_flapping(
            state_history,
            self.FLAPPING_FAILURE_STATES,
            now_monotonic=now_monotonic,
            window_seconds=flapping_window,
            min_transitions=flapping_min_transitions,
        ):
            recent_transitions = collect_recent_state_transitions(
                state_history,
                now_monotonic=now_monotonic,
                window_seconds=flapping_window,
            )
            history = recent_transitions[-(flapping_min_transitions + 1) :]
            reason = f"detected rapid failure state oscillation: {' -> '.join(history)}"
        if reason:
            if plugin_name not in plugins_to_recover:
                plugins_to_recover[plugin_name] = reason
    return plugins_to_recover


async def update_health_metrics(
    self: PluginGuardianInternalProtocol,
    *,
    check_context: GuardianCheckContext,
) -> None:
    logger = get_logger(GUARDIAN_LOGGER_NAME)
    plugin_names = collect_unlocked_guardian_plugin_names(check_context)
    semaphore = asyncio.Semaphore(GUARDIAN_HEALTH_METRIC_CONCURRENCY)

    async def _update_plugin_metrics(plugin_name: str) -> None:
        async with semaphore:
            state = get_plugin_status(check_context.plugin_states, plugin_name)
            circuit_breaker_snapshot = (
                await self.orchestrator.circuit_breakers.get_circuit_breaker_snapshot(
                    plugin_name,
                )
            )
            breaker_state = circuit_breaker_snapshot.get("state")
            health: Literal["ok", "recovering", "open", "quarantined", "disabled"]
            if state == ORCH_STATE_DISABLED:
                health = "disabled"
                value = 4
            elif state == ORCH_STATE_QUARANTINED:
                health = "quarantined"
                value = 3
            elif breaker_state == CircuitBreakerState.OPEN.value:
                health = "open"
                value = 3
            elif breaker_state == CircuitBreakerState.HALF_OPEN.value:
                health = "recovering"
                value = 2
            elif plugin_name not in check_context.recovery_in_progress:
                health = "ok"
                value = 1
            else:
                health = "recovering"
                value = 2
            await self.orchestrator.watchers.set_plugin_health_status(plugin_name, health)
            if self.metrics:
                self.metrics.set_gauge(*DIRECTOR_GAUGE_PLUGIN_HEALTH, plugin_name, value=value)

    results = await asyncio.gather(
        *[_update_plugin_metrics(plugin_name) for plugin_name in plugin_names],
        return_exceptions=True,
    )
    for plugin_name, result in zip(plugin_names, results, strict=False):
        if isinstance(result, BaseException):
            log_exception(
                logger,
                result,
                message="Failed to update guardian health metrics for plugin",
                operation=OPERATION_PLUGIN_GUARDIAN_UPDATE_HEALTH_METRICS,
                details={"plugin_name": plugin_name},
                level="warning",
            )
