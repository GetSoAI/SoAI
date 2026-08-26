"""SoAI - Orchestrator enforcement for tracked plugin backend processes [backend/orchestrator/lifecycle/tracked_backend_processes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Coroutine
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.orchestrator.stop_outcome import PluginStopOutcome
from core.runtime.backend_process_tracking import (
    cleanup_backend_process_identities,
    normalize_backend_process_pids,
    resolve_backend_process_identities,
)
from core.timing.constants import CONTROL_TIMEOUT_SEC
from orchestrator.lifecycle.graceful_stop_attempt import attempt_graceful_plugin_stop

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from core.plugins.protocols_instance import PluginInstanceProtocol

__all__ = (
    "perform_tracked_plugin_stop_logic",
    "supports_backend_process_tracking",
)

OPERATION = "orchestrator.perform_tracked_plugin_stop_logic"


def supports_backend_process_tracking(plugin_instance: PluginInstanceProtocol) -> bool:
    supports_tracking = bool(plugin_instance.SUPPORTS_BACKEND_PROCESS_TRACKING)
    supports_installation = bool(plugin_instance.SUPPORTS_BACKEND_INSTALLATION)
    return supports_tracking and supports_installation


async def perform_tracked_plugin_stop_logic(
    plugin_instance: PluginInstanceProtocol,
    *,
    plugin_name: str,
    database_plugins: DatabasePluginsProtocol,
    graceful_budget_sec: float,
    logger: LoggerProtocol,
    force_kill_budget_sec: float = float(CONTROL_TIMEOUT_SEC),
) -> PluginStopOutcome:
    graceful_succeeded = False
    stop_error_message: str | None = None
    attempt = await attempt_graceful_plugin_stop(
        plugin_instance,
        plugin_name=plugin_name,
        graceful_budget_sec=graceful_budget_sec,
        logger=logger,
    )
    if attempt.succeeded:
        graceful_succeeded = True
    else:
        stop_error_message = attempt.error_message
        if attempt.timed_out:
            logger.warning(
                "%s while stopping '%s'. Proceeding to identity-verified cleanup.",
                stop_error_message,
                plugin_name,
            )
        elif attempt.exception is not None:
            log_exception(
                logger,
                attempt.exception,
                message=(
                    f"{stop_error_message} while stopping '{plugin_name}'. "
                    "Proceeding to identity-verified cleanup."
                ),
                operation=OPERATION,
            )
    cleanup_deadline = time.monotonic() + force_kill_budget_sec
    try:
        outcome = await _perform_tracked_backend_cleanup(
            plugin_instance=plugin_instance,
            plugin_name=plugin_name,
            database_plugins=database_plugins,
            graceful_succeeded=graceful_succeeded,
            stop_error_message=stop_error_message,
            cleanup_deadline=cleanup_deadline,
            logger=logger,
        )
    except TimeoutError:
        outcome = PluginStopOutcome(
            terminated=False,
            message=(
                "Backend process cleanup exceeded the force-kill budget; refusing to mark "
                "the plugin as stopped."
            ),
        )
    return outcome


async def _perform_tracked_backend_cleanup(
    *,
    plugin_instance: PluginInstanceProtocol,
    plugin_name: str,
    database_plugins: DatabasePluginsProtocol,
    graceful_succeeded: bool,
    stop_error_message: str | None,
    cleanup_deadline: float,
    logger: LoggerProtocol,
) -> PluginStopOutcome:
    killed_any = False
    verified_cleanup_attempted = False
    identities = await database_plugins.get_runtime_processes(plugin_name)
    cleanup_identities = identities
    if not cleanup_identities:
        raw_pids = await _await_cleanup_budget(
            plugin_instance.get_backend_process_pids(),
            deadline=cleanup_deadline,
        )
        pids = normalize_backend_process_pids(raw_pids)
        if pids:
            resolved = resolve_backend_process_identities(
                pids,
                plugin_name=plugin_name,
                logger=logger,
            )
            if resolved:
                await _await_cleanup_budget(
                    database_plugins.set_runtime_processes(
                        plugin_name,
                        resolved,
                    ),
                    deadline=cleanup_deadline,
                )
                cleanup_identities = resolved
    if cleanup_identities:
        verified_cleanup_attempted = True
        cleanup_result = await _await_cleanup_budget(
            cleanup_backend_process_identities(
                cleanup_identities,
                plugin_name=plugin_name,
                logger=logger,
            ),
            deadline=cleanup_deadline,
        )
        killed_any = killed_any or bool(cleanup_result.killed)
        if not cleanup_result.succeeded:
            await _await_cleanup_budget(
                database_plugins.set_runtime_processes(
                    plugin_name,
                    cleanup_result.failed,
                ),
                deadline=cleanup_deadline,
            )
            return PluginStopOutcome(
                terminated=False,
                message="Backend process cleanup failed; refusing to mark the plugin as stopped.",
            )
    raw_pids = await _await_cleanup_budget(
        plugin_instance.get_backend_process_pids(),
        deadline=cleanup_deadline,
    )
    pids = normalize_backend_process_pids(raw_pids)
    if pids:
        resolved = resolve_backend_process_identities(
            pids,
            plugin_name=plugin_name,
            logger=logger,
        )
        if resolved:
            verified_cleanup_attempted = True
            await _await_cleanup_budget(
                database_plugins.set_runtime_processes(
                    plugin_name,
                    resolved,
                ),
                deadline=cleanup_deadline,
            )
            followup_result = await _await_cleanup_budget(
                cleanup_backend_process_identities(
                    resolved,
                    plugin_name=plugin_name,
                    logger=logger,
                ),
                deadline=cleanup_deadline,
            )
            killed_any = killed_any or bool(followup_result.killed)
            if not followup_result.succeeded:
                await _await_cleanup_budget(
                    database_plugins.set_runtime_processes(
                        plugin_name,
                        followup_result.failed,
                    ),
                    deadline=cleanup_deadline,
                )
                return PluginStopOutcome(
                    terminated=False,
                    message=(
                        "Backend process cleanup failed; refusing to mark the plugin as stopped."
                    ),
                )
    if (not graceful_succeeded) and (not verified_cleanup_attempted):
        return PluginStopOutcome(
            terminated=False,
            message=(
                stop_error_message
                or "Plugin stop failed and no backend process identities were available."
            ),
        )
    await _await_cleanup_budget(
        database_plugins.clear_runtime_processes(plugin_name),
        deadline=cleanup_deadline,
    )
    return PluginStopOutcome(
        terminated=True,
        message=stop_error_message or "Plugin stopped successfully.",
    )


async def _await_cleanup_budget[Result](
    awaitable: Awaitable[Result],
    *,
    deadline: float,
) -> Result:
    remaining_seconds = deadline - time.monotonic()
    if remaining_seconds <= 0:
        if isinstance(awaitable, Coroutine):
            awaitable.close()
        raise TimeoutError
    return await asyncio.wait_for(awaitable, timeout=remaining_seconds)
