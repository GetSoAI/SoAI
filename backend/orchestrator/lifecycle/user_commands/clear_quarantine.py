"""SoAI - Clear quarantine user command handler [backend/orchestrator/lifecycle/user_commands/clear_quarantine.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.events.types_plugins import ClearQuarantineCommand
from core.logging.trace import get_logger
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN,
    SchedulerWorkItem,
)
from core.state.circuit_breaker import CircuitBreakerState
from core.state.state_names import (
    ORCH_STATE_ERROR,
    ORCH_STATE_QUARANTINED,
)
from core.tasks.api_events import send_task_complete_event
from orchestrator.lifecycle.state_transition_publication import (
    publish_runtime_state_change_and_wait,
)
from orchestrator.lifecycle.user_commands.dependencies import (
    OrchestratorLifecycleUserCommandsDependencies,
)
from orchestrator.lifecycle.user_commands.plugin_activation_resolution import (
    resolve_clear_quarantine_activation_transition_or_none,
)
from orchestrator.lifecycle.user_commands.runner import run_lifecycle_command

__all__ = ("handle_clear_quarantine",)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.clear_quarantine"
OPERATION = "orchestrator.handle_clear_quarantine"


async def _reset_breaker_health(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    plugin_name: str,
) -> None:
    await deps.circuit_breakers.record_cb_success(plugin_name)
    await deps.watchers.set_plugin_health_status(plugin_name, "ok")
    await deps.watchers.clear_plugin_recovery_attempts(plugin_name)


async def _complete_reset_task(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    event: ClearQuarantineCommand,
    plugin_name: str,
    success: bool = True,
    error_message: str | None = None,
) -> None:
    await send_task_complete_event(
        event.reply_channel,
        error_message or f"Circuit breaker reset for plugin {plugin_name}",
        success=success,
        error_code=500 if not success else None,
        registry=deps.task_registry,
    )


async def handle_clear_quarantine(
    deps: OrchestratorLifecycleUserCommandsDependencies,
    *,
    event: ClearQuarantineCommand,
) -> list[SchedulerWorkItem]:
    logger = get_logger(LOGGER_NAME)
    plugin_name = event.plugin_name
    if not plugin_name:
        return []
    if not deps.orchestrator.plugin_manager.is_known_plugin(plugin_name):
        logger.debug("Ignoring event for unknown or purged plugin '%s'.", plugin_name)
        return []

    async def handler() -> SchedulerWorkItem:
        current_state = await deps.orchestrator.state_aggregator.get_plugin_status(plugin_name)
        if (
            current_state == ORCH_STATE_QUARANTINED
            and await deps.orchestrator.plugin_manager.is_clone_integrity_quarantined(plugin_name)
        ):
            await _complete_reset_task(
                deps,
                event=event,
                plugin_name=plugin_name,
                success=False,
                error_message=(
                    f"Could not reset circuit breaker for plugin {plugin_name}: "
                    "plugin is quarantined for clone integrity recovery."
                ),
            )
            return SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN, plugin_name)
        if current_state != ORCH_STATE_QUARANTINED:
            snapshot = await deps.circuit_breakers.get_circuit_breaker_snapshot(plugin_name)
            snapshot_state = snapshot.get("state")
            if not isinstance(snapshot_state, str):
                raise StateError(
                    "Circuit breaker snapshot is missing a valid state.",
                    operation=OPERATION,
                    details={"plugin_name": plugin_name},
                )
            if snapshot_state in (
                CircuitBreakerState.OPEN.value,
                CircuitBreakerState.HALF_OPEN.value,
            ):
                latest_state = await deps.orchestrator.state_aggregator.get_plugin_status(
                    plugin_name,
                )
                if latest_state == ORCH_STATE_QUARANTINED:
                    await _complete_reset_task(
                        deps,
                        event=event,
                        plugin_name=plugin_name,
                        success=False,
                        error_message=(
                            f"Could not reset circuit breaker for plugin {plugin_name}: "
                            "plugin entered quarantine during reset."
                        ),
                    )
                    return SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN, plugin_name)
                await _reset_breaker_health(deps, plugin_name=plugin_name)
                logger.info(
                    "Circuit breaker for plugin %s has been reset without state change.",
                    plugin_name,
                )
            await _complete_reset_task(deps, event=event, plugin_name=plugin_name)
            return SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN, plugin_name)
        transition = await resolve_clear_quarantine_activation_transition_or_none(
            plugin_manager=deps.orchestrator.plugin_manager,
            plugin_name=plugin_name,
            logger=logger,
        )
        if transition is None:
            await _complete_reset_task(
                deps,
                event=event,
                plugin_name=plugin_name,
                success=False,
                error_message=(
                    f"Could not reset circuit breaker for plugin {plugin_name}: "
                    "failed to validate plugin after quarantine clear."
                ),
            )
            return SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN, plugin_name)
        target_state = transition.target_state
        if target_state == ORCH_STATE_ERROR:
            await _complete_reset_task(
                deps,
                event=event,
                plugin_name=plugin_name,
                success=False,
                error_message=(
                    f"Could not reset circuit breaker for plugin {plugin_name}: "
                    "plugin validation failed after quarantine clear."
                ),
            )
            return SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN, plugin_name)
        await publish_runtime_state_change_and_wait(
            publisher=deps.lifecycle_publisher,
            plugin_name=plugin_name,
            new_state=target_state,
            reason=transition.reason,
        )
        await _reset_breaker_health(deps, plugin_name=plugin_name)
        logger.info("Circuit breaker for plugin %s has been reset by user command.", plugin_name)
        await _complete_reset_task(deps, event=event, plugin_name=plugin_name)
        return SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN, plugin_name)

    result = await run_lifecycle_command(
        deps,
        plugin_name=plugin_name,
        command=event,
        action_name="ClearQuarantine",
        handler=handler,
    )
    return [result] if result else []
