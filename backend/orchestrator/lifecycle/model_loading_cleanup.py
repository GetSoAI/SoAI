"""SoAI - Model loading cancellation-safe cleanup [backend/orchestrator/lifecycle/model_loading_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.state.state_names import ORCH_STATE_STOPPED, ORCH_STATE_STOPPING
from orchestrator.lifecycle.model_loading_transitions import (
    publish_model_load_stopped_terminal_state_if_valid,
    publish_stopping_if_valid,
    publish_terminal_state_if_valid,
)
from orchestrator.lifecycle.plugin_process_termination import (
    force_kill_plugin_backend_processes,
)
from orchestrator.lifecycle.tracked_backend_processes import (
    perform_tracked_plugin_stop_logic,
    supports_backend_process_tracking,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.orchestrator.protocols_lifecycle import (
        OrchestratorLifecyclePublisherProtocol,
    )
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.plugins.protocols_instance import PluginInstanceProtocol
    from core.state.protocols import StateAggregatorProtocol
    from core.state.state_names import PluginRuntimeStateName
    from orchestrator.lifecycle.model_loading_dependencies import (
        OrchestratorLifecycleModelLoadingDependencies,
    )

__all__ = (
    "CONCURRENT_LIFECYCLE_STATE_CHANGE_REASON",
    "publish_cancelled_model_load_terminal_state_if_valid",
    "stop_plugin_for_model_load_cleanup",
    "stop_started_plugin_for_concurrent_lifecycle_state_change",
    "stop_started_plugin_for_model_load_cleanup",
)

OPERATION = "orchestrator.start_plugin_and_load_model"
CONCURRENT_LIFECYCLE_STATE_CHANGE_REASON = "Concurrent lifecycle state change; stopping plugin."


async def stop_plugin_for_model_load_cleanup(
    *,
    plugin_instance: PluginInstanceProtocol,
    plugin_name: str,
    database_plugins: DatabasePluginsProtocol,
    publisher: OrchestratorLifecyclePublisherProtocol,
    state_aggregator: StateAggregatorProtocol,
    reason: str,
    publish_state_changes: bool,
    logger: LoggerProtocol,
    shutdown_event: asyncio.Event | None = None,
) -> bool:
    terminated = True
    state_publication_owned = publish_state_changes and (
        shutdown_event is None or not shutdown_event.is_set()
    )
    if state_publication_owned:
        stopping_confirmed = await publish_stopping_if_valid(
            plugin_name=plugin_name,
            publisher=publisher,
            state_aggregator=state_aggregator,
            reason=reason,
            logger=logger,
        )
    else:
        stopping_confirmed = False
    try:
        if supports_backend_process_tracking(plugin_instance):
            stop_outcome = await perform_tracked_plugin_stop_logic(
                plugin_instance,
                plugin_name=plugin_name,
                database_plugins=database_plugins,
                graceful_budget_sec=0.0,
                logger=logger,
            )
            terminated = bool(stop_outcome.terminated)
        else:
            terminated = await force_kill_plugin_backend_processes(
                plugin_instance,
                logger=logger,
                missing_pids_is_success=False,
            )
    except RECOVERABLE_EXCEPTIONS as stop_exception:
        terminated = False
        log_exception(
            logger,
            stop_exception,
            message="Failed stopping plugin backend processes during model load cleanup.",
            operation=OPERATION,
            details={"plugin": plugin_name},
            level="warning",
        )
    if not stopping_confirmed or (shutdown_event is not None and shutdown_event.is_set()):
        return terminated
    await publish_model_load_stopped_terminal_state_if_valid(
        plugin_instance=plugin_instance,
        terminated=terminated,
        stopped_reason="Plugin stopped after cancelled model load.",
        failed_reason="Plugin stop failed after cancelled model load.",
        operation="orchestrator.start_plugin_and_load_model.cleanup.persistent",
        plugin_name=plugin_name,
        publisher=publisher,
        state_aggregator=state_aggregator,
        logger=logger,
        previous_state_override=ORCH_STATE_STOPPING,
        shutdown_event=shutdown_event,
    )
    return terminated


async def publish_cancelled_model_load_terminal_state_if_valid(
    *,
    plugin_name: str,
    publisher: OrchestratorLifecyclePublisherProtocol,
    state_aggregator: StateAggregatorProtocol,
    logger: LoggerProtocol,
    reason: str,
    terminal_state: PluginRuntimeStateName = ORCH_STATE_STOPPED,
    terminal_reason: str = "Model load cancelled; plugin returned to STOPPED.",
    shutdown_event: asyncio.Event | None = None,
) -> None:
    if shutdown_event is not None and shutdown_event.is_set():
        return
    try:
        current_status = await state_aggregator.get_plugin_status(plugin_name)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed reading plugin state before cancelled model-load terminal publish (non-critical).",
            operation=OPERATION,
            details={"plugin": plugin_name},
            level="debug",
        )
        return
    if current_status == terminal_state:
        return
    stopping_confirmed = await publish_stopping_if_valid(
        plugin_name=plugin_name,
        publisher=publisher,
        state_aggregator=state_aggregator,
        reason=reason,
        logger=logger,
    )
    if not stopping_confirmed or (shutdown_event is not None and shutdown_event.is_set()):
        return
    await publish_terminal_state_if_valid(
        plugin_name=plugin_name,
        publisher=publisher,
        state_aggregator=state_aggregator,
        new_state=terminal_state,
        reason=terminal_reason,
        logger=logger,
        previous_state_override=ORCH_STATE_STOPPING,
    )


async def stop_started_plugin_for_model_load_cleanup(
    *,
    started_process: bool,
    plugin_instance: PluginInstanceProtocol | None,
    plugin_name: str,
    database_plugins: DatabasePluginsProtocol,
    publisher: OrchestratorLifecyclePublisherProtocol,
    state_aggregator: StateAggregatorProtocol,
    reason: str,
    publish_state_changes: bool,
    logger: LoggerProtocol,
    shutdown_event: asyncio.Event | None = None,
) -> bool:
    if not started_process or plugin_instance is None:
        return False
    return await stop_plugin_for_model_load_cleanup(
        plugin_instance=plugin_instance,
        plugin_name=plugin_name,
        database_plugins=database_plugins,
        publisher=publisher,
        state_aggregator=state_aggregator,
        reason=reason,
        publish_state_changes=publish_state_changes,
        logger=logger,
        shutdown_event=shutdown_event,
    )


async def stop_started_plugin_for_concurrent_lifecycle_state_change(
    deps: OrchestratorLifecycleModelLoadingDependencies,
    *,
    started_process: bool,
    plugin_instance: PluginInstanceProtocol | None,
    plugin_name: str,
    logger: LoggerProtocol,
) -> bool:
    return await stop_started_plugin_for_model_load_cleanup(
        started_process=started_process,
        plugin_instance=plugin_instance,
        plugin_name=plugin_name,
        database_plugins=deps.orchestrator.database_plugins,
        publisher=deps.lifecycle_publisher,
        state_aggregator=deps.orchestrator.state_aggregator,
        reason=CONCURRENT_LIFECYCLE_STATE_CHANGE_REASON,
        publish_state_changes=False,
        logger=logger,
    )
