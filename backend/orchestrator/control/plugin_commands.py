"""SoAI - Orchestrator plugin lifecycle commands and state event handlers [backend/orchestrator/control/plugin_commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.events.types_base import Event
from core.events.types_models_model_events import ModelParametersRequireReloadEvent
from core.events.types_plugins import (
    ClearQuarantineCommand,
    PluginInstallationStateChangedEvent,
    PluginLoadedEvent,
    PluginPurgedEvent,
    PluginRuntimeStateChangedEvent,
    PluginStoppedEvent,
    RequestPluginDisableCommand,
    RequestPluginEnableCommand,
    RequestPluginStopAndWaitCommand,
    StopAllPluginsCommand,
)
from core.events.types_system import ConfigReloadedEvent
from core.logging.trace import get_logger
from core.state.state_transition_sets import NON_STOPPABLE_STATES
from orchestrator.control.plugin_command_dependencies import (
    OrchestratorPluginCommandDependencies,
)
from orchestrator.control.plugin_config_reload import enqueue_plugin_config_reload
from orchestrator.control.plugin_lifecycle_command_tasks import (
    schedule_clear_quarantine_task,
    schedule_plugin_disable_task,
    schedule_plugin_enable_task,
    schedule_plugin_stop_task,
)
from orchestrator.control.plugin_queue_purge import (
    purge_all_requests_from_global_queues,
)
from orchestrator.control.plugin_queue_purge_dependencies import (
    PluginQueuePurgeDependencies,
)
from orchestrator.control.plugin_scheduler_work import schedule_work_items
from orchestrator.control.shutdown_stop_all import execute_shutdown_stop_all

__all__ = (
    "handle_clear_quarantine",
    "handle_model_parameters_require_reload",
    "handle_plugin_config_reloaded",
    "handle_plugin_disable_command",
    "handle_plugin_enable_command",
    "handle_plugin_purged",
    "handle_plugin_reloaded",
    "handle_plugin_state_change",
    "handle_plugin_stop_and_wait",
    "handle_plugin_stopped",
    "handle_stop_all_plugins",
)

LOGGER_NAME = "SoAI.orchestrator.control.plugin_commands"


async def handle_stop_all_plugins(
    event: Event,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not isinstance(event, StopAllPluginsCommand):
        return
    initiator = str(event.initiator or "user")
    shutdown_deadline: MonotonicDeadline | None = None
    if initiator == "shutdown":
        shutdown_deadline = deadline_after(deps.shutdown_stop_all_plugins_timeout_sec)
    if initiator == "shutdown":
        logger.info("Shutdown stop for all plugins initiated. Cancelling queued and active tasks.")
    else:
        logger.info("FORCE STOP ALL PLUGINS initiated. Cancelling all queued and active tasks.")
    fail_reason = (
        "All plugins are being stopped due to system shutdown."
        if initiator == "shutdown"
        else "All plugins are being stopped by administrator command."
    )
    purge_deps = PluginQueuePurgeDependencies(
        orchestrator=deps.orchestrator,
        queue=deps.queue,
        scheduler=deps.scheduler,
        active_inferences=deps.active_inferences,
        outcomes=deps.outcomes,
    )
    await purge_all_requests_from_global_queues(
        deps=purge_deps,
        terminal_reason=fail_reason,
        terminal_status="cancelled" if initiator == "shutdown" else "failed",
    )
    all_states = await deps.orchestrator.state_aggregator.get_all_plugin_states()
    plugins_to_stop = [
        name for name, data in all_states.items() if data.get("status") not in NON_STOPPABLE_STATES
    ]
    if not plugins_to_stop:
        logger.info("Received command to stop all plugins, but no stoppable plugins were found.")
        return
    plugins_to_stop = sorted(set(plugins_to_stop))
    if initiator == "shutdown":
        final_list = plugins_to_stop
        logger.info(
            "Issuing shutdown stop command for all non-disabled plugins: %s",
            final_list,
        )
    else:
        plugin_instance_tasks = [
            deps.orchestrator.plugin_manager.get_plugin_instance(plugin_name)
            for plugin_name in plugins_to_stop
        ]
        instances = await asyncio.gather(*plugin_instance_tasks, return_exceptions=False)
        persistent_plugins: set[str] = set()
        for plugin_name, instance in zip(plugins_to_stop, instances, strict=True):
            if instance is not None and bool(instance.PERSISTENT):
                persistent_plugins.add(plugin_name)
        final_list = [name for name in plugins_to_stop if name not in persistent_plugins]
        logger.info(
            "Issuing force stop command for all non-persistent, non-disabled plugins: %s",
            final_list,
        )
    stop_reason = (
        "Shutdown stop-all: stopping plugins."
        if initiator == "shutdown"
        else "Force stop all plugins command"
    )
    wait_for_state_changes = initiator != "shutdown"
    if initiator == "shutdown":
        if shutdown_deadline is None:
            shutdown_deadline = deadline_after(deps.shutdown_stop_all_plugins_timeout_sec)
        await execute_shutdown_stop_all(
            deps.lifecycle.shutdown,
            final_list,
            reason=stop_reason,
            deadline=shutdown_deadline,
        )
        return
    stop_timeout_sec: float | None = None
    stop_tasks = [
        deps.lifecycle.shutdown.stop_plugin(
            plugin_name=plugin_name,
            reason=stop_reason,
            force=True,
            wait_for_state_changes=wait_for_state_changes,
            stop_timeout_sec=stop_timeout_sec,
        )
        for plugin_name in final_list
    ]
    await asyncio.gather(*stop_tasks, return_exceptions=False)


async def handle_plugin_stop_and_wait(
    event: Event,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if not isinstance(event, RequestPluginStopAndWaitCommand):
        return
    await schedule_plugin_stop_task(event, deps=deps)


async def handle_clear_quarantine(
    event: Event,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if not isinstance(event, ClearQuarantineCommand):
        return
    await schedule_clear_quarantine_task(event, deps=deps)


async def handle_plugin_disable_command(
    command: Event,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if not isinstance(command, RequestPluginDisableCommand):
        return
    await schedule_plugin_disable_task(command, deps=deps)


async def handle_plugin_enable_command(
    command: Event,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if not isinstance(command, RequestPluginEnableCommand):
        return
    await schedule_plugin_enable_task(command, deps=deps)


async def handle_plugin_config_reloaded(
    event: Event,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if not isinstance(event, ConfigReloadedEvent):
        return
    if event.config_name == "core":
        return
    await enqueue_plugin_config_reload(event=event, deps=deps)


async def handle_model_parameters_require_reload(
    event: Event,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if not isinstance(event, ModelParametersRequireReloadEvent):
        return
    work_items = await deps.lifecycle.startup.handle_parameters_changed(event)
    await schedule_work_items(
        scheduler=deps.scheduler,
        work_items=work_items,
        operation="orchestrator_control.handle_model_parameters_require_reload",
    )


async def handle_plugin_state_change(
    event: Event,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if not isinstance(event, PluginRuntimeStateChangedEvent | PluginInstallationStateChangedEvent):
        return
    await deps.lifecycle.watchers.handle_state_change(event)


async def handle_plugin_stopped(
    event: Event,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if not isinstance(event, PluginStoppedEvent):
        return
    work_items = await deps.lifecycle.watchers.handle_plugin_stopped(event)
    await schedule_work_items(
        scheduler=deps.scheduler,
        work_items=work_items,
        operation="orchestrator_control.handle_plugin_stopped",
    )


async def handle_plugin_reloaded(
    event: Event,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if not isinstance(event, PluginLoadedEvent):
        return
    await deps.lifecycle.watchers.handle_plugin_reloaded(event)


async def handle_plugin_purged(
    event: Event,
    *,
    deps: OrchestratorPluginCommandDependencies,
) -> None:
    if not isinstance(event, PluginPurgedEvent):
        return
    await deps.lifecycle.watchers.handle_plugin_purged(event)
