"""SoAI - Orchestrator plugin backend process termination helpers [backend/orchestrator/lifecycle/plugin_process_termination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.backend_process_tracking import (
    cleanup_backend_process_identities,
    normalize_backend_process_pids,
    resolve_backend_process_identities,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from orchestrator.lifecycle.state_access.internal_protocols import (
        KillablePluginProcessProtocol,
    )

__all__ = ("force_kill_plugin_backend_processes",)

LOGGER_NAME = "SoAI.orchestrator.lifecycle.plugin_process_termination"
OPERATION = "orchestrator.lifecycle.plugin_process_termination.force_kill"


async def force_kill_plugin_backend_processes(
    plugin_instance: KillablePluginProcessProtocol,
    *,
    logger: LoggerProtocol | None = None,
    missing_pids_is_success: bool,
) -> bool:
    resolved_logger = logger if logger is not None else get_logger(LOGGER_NAME)
    raw_pids = await plugin_instance.get_backend_process_pids()
    pids = normalize_backend_process_pids(raw_pids)
    if not pids:
        if not missing_pids_is_success:
            resolved_logger.error(
                "Plugin '%s' reported no process IDs during force-kill escalation after a failed graceful stop.",
                plugin_instance.plugin_name,
            )
            return False
        resolved_logger.info(
            "Plugin '%s' has no active process IDs during force-kill escalation; treating it as stopped.",
            plugin_instance.plugin_name,
        )
        return True
    try:
        identities = resolve_backend_process_identities(
            pids,
            plugin_name=plugin_instance.plugin_name,
            logger=resolved_logger,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            resolved_logger,
            exception,
            message="Failed to resolve plugin backend process identities before force-kill.",
            operation=OPERATION,
            details={"plugin": plugin_instance.plugin_name},
        )
        return False
    if not identities:
        return True
    cleanup_result = await cleanup_backend_process_identities(
        identities,
        plugin_name=plugin_instance.plugin_name,
        logger=resolved_logger,
    )
    return cleanup_result.succeeded
