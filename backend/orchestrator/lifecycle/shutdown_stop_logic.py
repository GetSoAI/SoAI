"""SoAI - Orchestrator plugin stop logic [backend/orchestrator/lifecycle/shutdown_stop_logic.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.orchestrator.stop_outcome import PluginStopOutcome
from core.runtime.backend_process_tracking_db import (
    cleanup_tracked_backend_processes_from_database,
)
from core.timing.constants import CONTROL_TIMEOUT_SEC, LONG_REQUEST_TIMEOUT_SEC
from orchestrator.lifecycle.event_shutdown.internal_protocols import (
    OrchestratorShutdownStopLogicDependenciesProtocol,
)
from orchestrator.lifecycle.graceful_stop_attempt import attempt_graceful_plugin_stop
from orchestrator.lifecycle.plugin_process_termination import (
    force_kill_plugin_backend_processes,
)
from orchestrator.lifecycle.tracked_backend_processes import (
    perform_tracked_plugin_stop_logic,
    supports_backend_process_tracking,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "perform_plugin_stop_logic",
    "resolve_stop_budget_split",
)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.shutdown_stop_logic"
OPERATION_ORCHESTRATOR_PERFORM_PLUGIN_STOP_LOGIC = "orchestrator.perform_plugin_stop_logic"
FORCE_KILL_BUDGET_FRACTION = 0.2


def resolve_stop_budget_split(stop_timeout_total: float) -> tuple[float, float]:
    force_kill_budget_sec = min(
        float(CONTROL_TIMEOUT_SEC),
        stop_timeout_total * FORCE_KILL_BUDGET_FRACTION,
    )
    graceful_budget_sec = max(0.0, stop_timeout_total - force_kill_budget_sec)
    return graceful_budget_sec, force_kill_budget_sec


async def perform_plugin_stop_logic(
    deps: OrchestratorShutdownStopLogicDependenciesProtocol,
    health_check_config: JSONDict,
    plugin_name: str,
    *,
    stop_timeout_sec: float | None,
) -> PluginStopOutcome:
    logger = get_logger(LOGGER_NAME)
    try:
        plugin_instance = await deps.orchestrator.plugin_manager.get_plugin_instance(plugin_name)
        if not plugin_instance:
            record = await deps.orchestrator.database_plugins.get_plugin_by_name(plugin_name)
            supports_process_tracking = bool(
                record and record.get("supports_backend_process_tracking"),
            )
            if supports_process_tracking:
                cleanup_result = await cleanup_tracked_backend_processes_from_database(
                    deps.orchestrator.database_plugins,
                    plugin_name=plugin_name,
                    logger=logger,
                )
                if cleanup_result is not None and (not cleanup_result.succeeded):
                    return PluginStopOutcome(
                        terminated=False,
                        message="Plugin instance is not loaded and tracked backend process cleanup failed.",
                    )
            return PluginStopOutcome(
                terminated=True,
                message="Plugin instance is not loaded.",
            )
        supports_process_tracking = supports_backend_process_tracking(plugin_instance)
        command_timeouts = health_check_config.get("COMMAND_TIMEOUTS_SEC")
        command_timeouts_map: dict[str, JSONValue] = (
            dict(command_timeouts) if isinstance(command_timeouts, dict) else {}
        )
        raw_timeout = command_timeouts_map.get("PLUGIN_STOP", LONG_REQUEST_TIMEOUT_SEC)
        configured_timeout: float
        try:
            configured_timeout = (
                float(raw_timeout)
                if isinstance(raw_timeout, int | float | str)
                else float(LONG_REQUEST_TIMEOUT_SEC)
            )
        except (TypeError, ValueError):
            configured_timeout = float(LONG_REQUEST_TIMEOUT_SEC)
        budget_timeout: float | None = None
        if stop_timeout_sec is not None:
            try:
                budget_timeout = float(stop_timeout_sec)
            except (TypeError, ValueError) as exception:
                raise ValueError("stop_timeout_sec must be numeric.") from exception
            if budget_timeout <= 0:
                raise ValueError("stop_timeout_sec must be greater than 0.")
        stop_timeout_total = (
            min(configured_timeout, budget_timeout)
            if budget_timeout is not None
            else configured_timeout
        )
        graceful_budget_sec, force_kill_budget_sec = resolve_stop_budget_split(stop_timeout_total)
        if supports_process_tracking:
            return await perform_tracked_plugin_stop_logic(
                plugin_instance,
                plugin_name=plugin_name,
                database_plugins=deps.orchestrator.database_plugins,
                graceful_budget_sec=graceful_budget_sec,
                force_kill_budget_sec=force_kill_budget_sec,
                logger=logger,
            )
        attempt = await attempt_graceful_plugin_stop(
            plugin_instance,
            plugin_name=plugin_name,
            graceful_budget_sec=graceful_budget_sec,
            logger=logger,
        )
        if attempt.succeeded:
            return PluginStopOutcome(
                terminated=True,
                message="Plugin stopped gracefully.",
            )
        stop_error_message = attempt.error_message or "Plugin stop failed."
        if (not attempt.timed_out) and attempt.exception is not None:
            log_exception(
                logger,
                attempt.exception,
                message=f"{stop_error_message} while stopping '{plugin_name}'. Escalating to force-kill.",
                operation=OPERATION_ORCHESTRATOR_PERFORM_PLUGIN_STOP_LOGIC,
            )
        else:
            logger.warning(
                "%s while stopping '%s'. Escalating to force-kill.",
                stop_error_message,
                plugin_name,
            )
        try:
            force_kill_succeeded = await asyncio.wait_for(
                force_kill_plugin_backend_processes(
                    plugin_instance,
                    logger=logger,
                    missing_pids_is_success=False,
                ),
                timeout=force_kill_budget_sec,
            )
        except TimeoutError:
            force_kill_succeeded = False
        if not force_kill_succeeded:
            failure_message = (
                f"{stop_error_message}. Force-kill failed to terminate the plugin process."
            )
            logger.error(
                "Plugin '%s' could not be terminated after force-kill escalation.",
                plugin_name,
            )
            return PluginStopOutcome(
                terminated=False,
                message=failure_message,
            )
        logger.info("Plugin '%s' terminated after forced kill.", plugin_name)
        return PluginStopOutcome(
            terminated=True,
            message=stop_error_message,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Critical error during plugin stop logic for {plugin_name}",
            operation=OPERATION_ORCHESTRATOR_PERFORM_PLUGIN_STOP_LOGIC,
        )
        return PluginStopOutcome(
            terminated=False,
            message=project_public_exception(exception).message,
        )
