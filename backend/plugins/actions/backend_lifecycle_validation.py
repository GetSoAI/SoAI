"""SoAI - Plugin backend lifecycle validation helpers [backend/plugins/actions/backend_lifecycle_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import shutil

from core.concurrency.joined_thread_call import run_joined_thread_call
from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.status_mapping import error_type_to_status_code
from core.events.types_base import Event
from core.filesystem.async_queries import async_path_exists
from core.logging.trace import get_logger
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.state.state_names import (
    PLUGIN_STATE_BACKEND_UPDATING,
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
    if plugin_instance is not None:
        await plugin_instance.cleanup_partial_installation()
        logger.debug("Called cleanup_partial_installation for plugin '%s'.", plugin_name)
    if await async_path_exists(temp_path):
        await run_joined_thread_call(
            shutil.rmtree,
            temp_path,
            task_name="plugin-partial-installation-cleanup",
            retain_resources_until_complete=True,
        )
        logger.info("Cleaned up temporary installation directory: %s", temp_path)


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
    recovering_update: bool = False,
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
                if (
                    recovering_update
                    and action_name == "update_backend"
                    and current_state == PLUGIN_STATE_BACKEND_UPDATING
                ):
                    return True
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
