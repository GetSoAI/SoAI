"""SoAI - Orchestrator watcher plugin event handlers [backend/orchestrator/lifecycle/watcher_event_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.events.types_plugins import (
    PluginLoadedEvent,
    PluginPurgedEvent,
    PluginStoppedEvent,
)
from core.logging.trace import get_logger
from core.orchestrator.scheduler_work import (
    SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN,
    SchedulerWorkItem,
)
from core.state.state_names import ORCH_STATE_STOPPED
from orchestrator.lifecycle.event_shutdown.internal_protocols import (
    OrchestratorWatcherEventHandlerProtocol,
)

__all__ = (
    "handle_plugin_purged_event",
    "handle_plugin_reloaded_event",
    "handle_plugin_stopped_event",
)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.watcher_event_handlers"


async def handle_plugin_stopped_event(
    watchers: OrchestratorWatcherEventHandlerProtocol,
    event: PluginStoppedEvent,
) -> list[SchedulerWorkItem]:
    logger = get_logger(LOGGER_NAME)
    plugin_name = event.plugin_name
    if not plugin_name:
        return []
    if not watchers.deps.orchestrator.plugin_manager.is_known_plugin(plugin_name):
        logger.debug("Ignoring event for unknown or purged plugin '%s'.", plugin_name)
        return []
    async with watchers.deps.state.plugins_context() as plugin_state:
        state = plugin_state.plugin_states.get(plugin_name)
        if state is not None:
            state.loaded_model_universal_id = None
            state.last_request_universal_id = None
            state.loaded_parameters = None
            state.parameter_version = None
        plugin_state.idle_plugins.pop(plugin_name, None)
    await watchers.deps.lifecycle_publisher.publish_runtime_state_change(
        plugin_name,
        ORCH_STATE_STOPPED,
        "Plugin stop process completed.",
    )
    return [SchedulerWorkItem(SCHEDULER_WORK_TYPE_EVALUATE_PLUGIN, plugin_name)]


async def handle_plugin_reloaded_event(
    watchers: OrchestratorWatcherEventHandlerProtocol,
    event: PluginLoadedEvent,
) -> None:
    logger = get_logger(LOGGER_NAME)
    plugin_name = event.plugin_name
    if (not plugin_name) or (
        not watchers.deps.orchestrator.plugin_manager.is_known_plugin(plugin_name)
    ):
        logger.debug("Ignoring event for unknown or purged plugin '%s'.", plugin_name)
        return
    watchers.deps.capacity.mark_plugin_capacity_stale(plugin_name)


async def handle_plugin_purged_event(
    watchers: OrchestratorWatcherEventHandlerProtocol,
    event: PluginPurgedEvent,
) -> None:
    logger = get_logger(LOGGER_NAME)
    plugin_name = event.plugin_name
    if not plugin_name:
        return
    logger.debug(
        "Received purge event for plugin '%s'. Cleaning up director state.",
        plugin_name,
    )
    await watchers.discard_plugin_runtime_mutations(plugin_name)
    await watchers.deps.state.pop_plugin_state(plugin_name)
    await watchers.deps.state.pop_idle_plugin(plugin_name)
    await watchers.deps.state.pop_circuit_breaker(plugin_name)
    await watchers.deps.state.pop_recovery_attempts(plugin_name)
    await watchers.deps.state.remove_lock_entries(plugin_name)
    await watchers.deps.capacity.remove_plugin_capacity_state(plugin_name)
