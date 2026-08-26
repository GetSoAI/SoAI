"""SoAI - Plugin worker fault state transitions [backend/plugins/worker/controller_faults.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.state.state_names import (
    ORCH_STATE_ERROR,
    PLUGIN_STATE_BACKEND_NOT_INSTALLED,
    PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
    PLUGIN_STATE_DELETE_ERROR,
    PLUGIN_STATE_INSTALL_ERROR,
    PLUGIN_STATE_LOAD_ERROR,
    PLUGIN_STATE_NOT_DETECTED,
    PLUGIN_STATE_UPDATE_ERROR,
)
from core.state.state_transition_graph import get_valid_state_transitions
from plugins.manager.alias_map import update_alias_map
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.publication_wait import wait_for_plugin_state_publication

__all__ = ("mark_managed_runtime_failed", "mark_worker_crashed")

LOGGER_NAME = "SoAI.plugins.worker.controller_faults"
OPERATION_WORKER_CRASH_TRANSITION = "plugins.worker.controller.worker_crash_transition"
OPERATION_WORKER_CRASH_UNREGISTER_PARAMETERS = (
    "plugins.worker.controller.worker_crash_unregister_parameters"
)
OPERATION_WORKER_CRASH_DETACH_LOG_STREAMING = (
    "plugins.worker.controller.worker_crash_detach_log_streaming"
)
OPERATION_WORKER_CRASH_UPDATE_ALIASES = "plugins.worker.controller.worker_crash_update_aliases"
CRASH_TRANSITION_PRESERVED_STATES: frozenset[str] = frozenset(
    (
        PLUGIN_STATE_INSTALL_ERROR,
        PLUGIN_STATE_LOAD_ERROR,
        PLUGIN_STATE_UPDATE_ERROR,
        PLUGIN_STATE_BACKEND_NOT_INSTALLED,
        PLUGIN_STATE_BACKEND_UNINSTALL_ERROR,
        PLUGIN_STATE_DELETE_ERROR,
        PLUGIN_STATE_NOT_DETECTED,
    ),
)


async def mark_worker_crashed(
    manager: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    returncode: int | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    transition_exception: BaseException | None = None
    try:
        await _transition_crashed_plugin(manager, plugin_name, returncode)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message=(
                "Failed to transition crashed plugin worker state; "
                "continuing crash reconciliation."
            ),
            operation=OPERATION_WORKER_CRASH_TRANSITION,
            details={"plugin_name": plugin_name, "returncode": returncode},
            level="warning",
        )
        transition_exception = exception
    await _unregister_crashed_plugin_parameters(manager, plugin_name)
    await _detach_crashed_plugin_log_streaming(manager, plugin_name)
    await _update_aliases_after_crash(manager, plugin_name)
    if transition_exception is not None:
        raise transition_exception


async def mark_managed_runtime_failed(
    manager: PluginManagerRuntimeProtocol,
    *,
    plugin_name: str,
    reason: str,
    exit_status: int | None,
) -> bool:
    if manager.dependencies.infrastructure.lifecycle.shutdown_event.is_set():
        return False
    if not await _crash_transition_is_allowed(manager, plugin_name):
        return False
    receipt = await manager.transition_plugin_manager_state(
        plugin_name,
        ORCH_STATE_ERROR,
        reason,
    )
    await wait_for_plugin_state_publication(receipt)
    get_logger(LOGGER_NAME).error(
        "Plugin-managed runtime failed for '%s' with exit status %s.",
        plugin_name,
        exit_status,
    )
    return True


async def _unregister_crashed_plugin_parameters(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        await manager.dependencies.models.parameter_manager.unregister_plugin_parameters(
            plugin_name,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to unregister parameters for crashed plugin worker.",
            operation=OPERATION_WORKER_CRASH_UNREGISTER_PARAMETERS,
            details={"plugin_name": plugin_name},
            level="warning",
        )


async def _detach_crashed_plugin_log_streaming(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> None:
    log_manager = manager.dependencies.core.log_manager
    if log_manager is None:
        return
    logger = get_logger(LOGGER_NAME)
    try:
        await asyncio.to_thread(log_manager.detach_streaming_handler_from_plugin, plugin_name)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to detach log streaming for crashed plugin worker.",
            operation=OPERATION_WORKER_CRASH_DETACH_LOG_STREAMING,
            details={"plugin_name": plugin_name},
            level="warning",
        )


async def _update_aliases_after_crash(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        await update_alias_map(manager)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to update aliases after plugin worker crash.",
            operation=OPERATION_WORKER_CRASH_UPDATE_ALIASES,
            details={"plugin_name": plugin_name},
            level="warning",
        )


async def _transition_crashed_plugin(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    returncode: int | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if manager.dependencies.infrastructure.lifecycle.shutdown_event.is_set():
        return
    if not await _crash_transition_is_allowed(manager, plugin_name):
        return
    try:
        receipt = await manager.transition_plugin_manager_state(
            plugin_name,
            ORCH_STATE_ERROR,
            "Plugin worker exited unexpectedly.",
        )
        await wait_for_plugin_state_publication(receipt)
    except RECOVERABLE_EXCEPTIONS as exception:
        if not await _crash_transition_is_allowed(manager, plugin_name):
            return
        log_exception(
            logger,
            exception,
            message="Failed to mark crashed plugin worker as unavailable.",
            operation=OPERATION_WORKER_CRASH_TRANSITION,
            details={"plugin_name": plugin_name, "returncode": returncode},
            level="error",
        )
        raise


async def _crash_transition_is_allowed(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> bool:
    state_value = await manager.dependencies.infrastructure.state_aggregator.get_plugin_status(
        plugin_name,
    )
    if state_value in CRASH_TRANSITION_PRESERVED_STATES:
        return False
    return ORCH_STATE_ERROR in get_valid_state_transitions(state_value)
