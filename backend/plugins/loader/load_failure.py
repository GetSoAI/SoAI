"""SoAI - Plugin load failure cleanup and state transition [backend/plugins/loader/load_failure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Never

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_waiting import publication_completion_deadline
from core.logging.protocols import TraceLogger
from core.state.state_names import PLUGIN_STATE_INCOMPATIBLE, PLUGIN_STATE_LOAD_ERROR
from plugins.manager.instances import clear_loaded_plugin_state
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = ("handle_plugin_load_failure",)

OPERATION_PLUGIN_LOADER_LOAD_PLUGIN = "plugin_loader.load_plugin"
OPERATION_PLUGIN_LOADER_LOAD_PLUGIN_LOAD_ERROR_TRANSITION = (
    "plugin_loader.load_plugin.load_error_transition"
)


async def handle_plugin_load_failure(
    *,
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    exception: Exception,
    parameter_schema_registered: bool,
    publish_failure_state: bool,
    logger: TraceLogger,
) -> Never:
    load_error_transition_failure: BaseException | None = None
    record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    if (
        publish_failure_state
        and record
        and record.get("state")
        not in {
            PLUGIN_STATE_LOAD_ERROR,
            PLUGIN_STATE_INCOMPATIBLE,
        }
    ):
        logger.warning(
            "Plugin '%s' failed to load after being recorded. Marking as LOAD_ERROR.",
            plugin_name,
        )
        try:
            receipt = await manager.transition_plugin_manager_state(
                plugin_name,
                PLUGIN_STATE_LOAD_ERROR,
                "Plugin load failed.",
            )
            if receipt is not None:
                await receipt.wait_for_completion(publication_completion_deadline())
        except RECOVERABLE_EXCEPTIONS as transition_failure:
            log_exception(
                logger,
                transition_failure,
                message="Failed to persist authoritative LOAD_ERROR transition for plugin.",
                operation=OPERATION_PLUGIN_LOADER_LOAD_PLUGIN_LOAD_ERROR_TRANSITION,
                details={"plugin_name": plugin_name},
                level="error",
            )
            load_error_transition_failure = transition_failure
    await clear_loaded_plugin_state(manager, plugin_name)
    log_exception(
        logger,
        exception,
        message=f"Failed to load plugin '{plugin_name}'",
        operation=OPERATION_PLUGIN_LOADER_LOAD_PLUGIN,
        details={"plugin": plugin_name},
    )
    if parameter_schema_registered:
        await manager.dependencies.models.parameter_manager.unregister_plugin_parameters(
            plugin_name,
        )
    if load_error_transition_failure is not None:
        raise StateError(
            "Plugin load failed and LOAD_ERROR transition could not be persisted.",
        ) from load_error_transition_failure
    raise exception
