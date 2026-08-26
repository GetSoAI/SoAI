"""SoAI - Plugin backend lifecycle validation helpers [backend/plugins/actions/backend_lifecycle_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import inspect
import shutil

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.status_mapping import error_type_to_status_code
from core.events.types_base import Event
from core.filesystem.async_queries import async_path_exists
from core.logging.trace import get_logger
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.state.state_names import (
    PLUGIN_STATE_NOT_DETECTED,
    resolve_plugin_runtime_state_name,
)
from core.state.state_transition_sets import ALL_TRANSIENT_STATES
from plugins.actions.progress import send_completion_with_task
from plugins.manager.compatibility import compatibility_from_record
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = ()

LOGGER_NAME = "SoAI.plugins.actions.backend_lifecycle_validation"
OPERATION_PLUGIN_ACTIONS_CLEANUP_PARTIAL_INSTALLATION = (
    "plugin_actions.cleanup_partial_installation"
)
OPERATION_PLUGIN_ACTIONS_CLEANUP_PARTIAL_INSTALLATION_PLUGIN_CALLBACK = (
    "plugin_actions.cleanup_partial_installation.plugin_callback"
)
OPERATION_PLUGIN_ACTIONS_CLEANUP_PARTIAL_INSTALLATION_REMOVE_TEMP_PATH = (
    "plugin_actions.cleanup_partial_installation.remove_temp_path"
)


async def cleanup_partial_installation(
    manager: PluginManagerRuntimeProtocol,
    plugin_instance: PluginInstanceProtocol | None,
    plugin_name: str,
    action: str,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if action not in ["install_backend", "update_backend"]:
        return
    install_path = plugin_instance.install_path if plugin_instance else None
    if not install_path:
        try:
            if info := await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name):
                info_path = info.get("install_path")
                if isinstance(info_path, str) and info_path:
                    install_path = info_path
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to read install_path during partial installation cleanup (non-critical).",
                operation=OPERATION_PLUGIN_ACTIONS_CLEANUP_PARTIAL_INSTALLATION,
                details={"plugin_name": plugin_name},
                level="debug",
            )
    if not isinstance(install_path, str) or not install_path:
        logger.debug(
            "Could not determine install path for '%s'; skipping partial installation cleanup.",
            plugin_name,
        )
        return
    temp_path = f"{install_path}_temp"
    cleanup_callback = None
    if plugin_instance is not None:
        try:
            cleanup_callback = plugin_instance.cleanup_partial_installation
        except AttributeError:
            cleanup_callback = None
    if callable(cleanup_callback):
        try:
            result = cleanup_callback()
            if inspect.iscoroutine(result):
                await result
            logger.debug("Called cleanup_partial_installation for plugin '%s'.", plugin_name)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Plugin cleanup_partial_installation failed during lifecycle cleanup.",
                operation=OPERATION_PLUGIN_ACTIONS_CLEANUP_PARTIAL_INSTALLATION_PLUGIN_CALLBACK,
                details={"plugin_name": plugin_name, "action": action},
                level="warning",
            )
    if await async_path_exists(temp_path):
        try:
            await uncancel_and_wait(asyncio.to_thread(shutil.rmtree, temp_path))
            logger.info("Cleaned up temporary installation directory: %s", temp_path)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to clean up temporary installation directory.",
                operation=OPERATION_PLUGIN_ACTIONS_CLEANUP_PARTIAL_INSTALLATION_REMOVE_TEMP_PATH,
                details={"temp_path": temp_path, "plugin_name": plugin_name},
                level="warning",
            )


async def validate_action_for_state_async(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    action_name: str,
    reply_channel: asyncio.Queue[Event],
    task_id: str | None = None,
    *,
    emit_error_event: bool = True,
    finalize_task: bool = True,
    mutation_fencing_token: int | None = None,
) -> bool:
    error_type: ErrorType | None = None
    error_message: str | None = None
    plugin_info = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    if not plugin_info:
        error_type = ErrorType.NOT_FOUND
        error_message = f"Plugin '{plugin_name}' not found."
    else:
        current_state_value = plugin_info.get("state")
        current_state_name = (
            current_state_value
            if isinstance(current_state_value, str) and current_state_value
            else PLUGIN_STATE_NOT_DETECTED
        )
        current_state = resolve_plugin_runtime_state_name(current_state_name)
        if current_state is None:
            error_type = ErrorType.SERVER_ERROR
            error_message = (
                f"Plugin '{plugin_name}' has an invalid persisted state '{current_state_name}'. "
                "This indicates database corruption or a mismatched schema."
            )
        else:
            compatibility_check = compatibility_from_record(plugin_info)
            if (
                compatibility_check.reason
                and (not compatibility_check.is_overridden)
                and (action_name not in {"delete", "force_cleanup"})
            ):
                error_type = ErrorType.PLUGIN_UNAVAILABLE
                error_message = (
                    compatibility_check.message or f"Plugin '{plugin_name}' is incompatible."
                )
            else:
                display_name = plugin_info.get("name", plugin_name)
                action_str = action_name.replace("_", " ")
                if current_state in ALL_TRANSIENT_STATES and action_name not in {
                    "remove_backend",
                    "disable",
                    "delete",
                    "force_cleanup",
                }:
                    error_type = ErrorType.LOCKED
                    error_message = f"Cannot {action_str} for plugin '{display_name}' while it is in a transient state ('{current_state}'). Please wait."
                else:
                    allowed = manager.policy.allowed_actions_by_state.get(current_state)
                    if allowed and action_name not in allowed:
                        error_type = ErrorType.CONFLICT
                        error_message = f"Action '{action_str}' is not permitted for plugin '{display_name}' while it is in the '{current_state}' state."
    if error_type is not None and error_message is not None:
        task_helpers = manager.dependencies.infrastructure.task_helpers
        if emit_error_event:
            await task_helpers.send_error_event(reply_channel, error_message, error_type)
        if task_id and finalize_task:
            await send_completion_with_task(
                reply_channel,
                task_id,
                success=False,
                message=error_message,
                error_code=error_type_to_status_code(error_type),
                mutation_fencing_token=mutation_fencing_token,
                task_registry=manager.dependencies.infrastructure.task_registry,
                send_task_complete_event_callable=task_helpers.send_task_complete_event,
            )
        return False
    return True
