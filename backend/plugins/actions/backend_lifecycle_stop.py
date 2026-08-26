"""SoAI - Plugin backend lifecycle stop operations [backend/plugins/actions/backend_lifecycle_stop.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.orchestrator.stop_outcome import PluginStopOutcome
from core.runtime.backend_process_tracking_db import (
    cleanup_tracked_backend_processes_from_database,
)
from core.state.state_transition_sets import RUNTIME_TERMINATED_STATES
from core.timing.constants import MODERATE_DELAY_SEC
from plugins.actions.progress import send_progress_with_task

if TYPE_CHECKING:
    from core.events.types_base import Event
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("stop_plugin_if_running",)

LOGGER_NAME = "SoAI.plugins.actions.backend_lifecycle_stop"


async def stop_plugin_if_running(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    reply_channel: asyncio.Queue[Event] | None,
    *,
    task_id: str | None = None,
    safe_states: frozenset[str] = RUNTIME_TERMINATED_STATES,
    exclude_cancellation_ids: frozenset[str] = frozenset(),
) -> None:
    logger = get_logger(LOGGER_NAME)
    current_state = await manager.dependencies.infrastructure.state_aggregator.get_plugin_status(
        plugin_name,
    )
    if isinstance(current_state, str) and current_state in safe_states:
        logger.info(
            "Plugin '%s' is already in a safe, stopped state ('%s'). Skipping stop command.",
            plugin_name,
            current_state,
        )
        record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
        supports_process_tracking = bool(record and record.get("supports_backend_process_tracking"))
        if supports_process_tracking:
            cleanup_result = await cleanup_tracked_backend_processes_from_database(
                manager.dependencies.databases.plugins,
                plugin_name=plugin_name,
                logger=logger,
            )
            if cleanup_result is not None and (not cleanup_result.succeeded):
                raise StateError(
                    "Refusing to proceed: tracked backend process cleanup failed for a plugin in a stopped/safe state.",
                    operation="plugins.actions.backend_lifecycle_stop.stop_plugin_if_running",
                    details={"plugin_name": plugin_name, "state": current_state},
                )
        return
    try:
        orchestrator_lifecycle = manager.orchestrator_lifecycle
    except AttributeError:
        orchestrator_lifecycle = None
    if orchestrator_lifecycle is None:
        raise StateError("Orchestrator lifecycle is not bound for stop operation.")
    shutdown = None
    try:
        shutdown = orchestrator_lifecycle.shutdown
    except AttributeError:
        shutdown = None
    try:
        stop_plugin = shutdown.stop_plugin if shutdown is not None else None
    except AttributeError:
        stop_plugin = None
    if not callable(stop_plugin):
        raise StateError("Orchestrator lifecycle is required to stop running plugins.")
    display_name = await manager.get_plugin_display_name(plugin_name)
    cancelled_count = await manager.dependencies.infrastructure.lifecycle.cancel_plugin_tasks(
        plugin_name,
        f"Cancelling for lifecycle operation on '{display_name}'",
        exclude_cancellation_ids=exclude_cancellation_ids,
    )
    if cancelled_count > 0:
        logger.info(
            "Cancelled %s active lifecycle task(s) for plugin '%s'.",
            cancelled_count,
            display_name,
        )
        await send_progress_with_task(
            reply_channel,
            task_id,
            5,
            f"Cancelled {cancelled_count} pending task(s)...",
            manager.dependencies.infrastructure.task_registry,
            manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
        )
        await asyncio.sleep(MODERATE_DELAY_SEC)
    await send_progress_with_task(
        reply_channel,
        task_id,
        10,
        f"Plugin '{display_name}' is running. Requesting force stop...",
        manager.dependencies.infrastructure.task_registry,
        manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
    )
    stop_plugin_result = stop_plugin(
        plugin_name,
        reason="Force stopping for plugin lifecycle operation",
        publish_state_changes=True,
        force=True,
    )
    if not inspect.isawaitable(stop_plugin_result):
        raise StateError("Orchestrator lifecycle stop_plugin must return an awaitable.")
    stop_plugin_outcome = await stop_plugin_result
    if not isinstance(stop_plugin_outcome, PluginStopOutcome):
        raise StateError("Orchestrator lifecycle stop_plugin returned an invalid outcome.")
    if not stop_plugin_outcome.terminated:
        raise StateError(
            f"Orchestrator reported unsuccessful stop for '{display_name}'.",
            operation="plugins.actions.backend_lifecycle_stop.stop_plugin_if_running",
            details={
                "plugin_name": plugin_name,
                "message": stop_plugin_outcome.message,
            },
        )
    await send_progress_with_task(
        reply_channel,
        task_id,
        20,
        "Plugin process stopped.",
        manager.dependencies.infrastructure.task_registry,
        manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
    )
