"""SoAI - Plugin upload task handler with validation and installation [backend/plugins/actions/upload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_plugins import UploadPluginCommand
from core.files.move_with_cancellation import (
    MoveFileCommittedAfterCancellationError,
)
from core.files.operations import async_remove_if_exists
from core.logging.trace import get_logger
from core.tasks.errors import TaskIDCollisionError
from plugins.actions.progress import (
    create_task_progress_sender,
    notify_operation_cancelled,
    send_completion_with_task,
    send_success_completion_for_plugin_manager,
)
from plugins.actions.upload_cleanup import (
    UploadExecutionState,
    rollback_plugin_upload,
)
from plugins.actions.upload_steps import perform_plugin_upload_steps
from plugins.actions.upload_task_collision import handle_upload_task_id_collision
from plugins.actions.upload_validation import (
    UploadedPluginDisposition,
    normalize_upload_target,
    reject_upload_preflight_if_needed,
    resolve_upload_failure_code,
    resolve_upload_failure_message,
    resolve_upload_task_id,
)

if TYPE_CHECKING:
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ()

LOGGER_NAME = "SoAI.plugins.actions.upload"
OPERATION = "plugin_flow.process_upload_plugin_async"


async def process_upload_plugin_async(
    manager: PluginManagerRuntimeProtocol,
    command: UploadPluginCommand,
) -> None:
    logger = get_logger(LOGGER_NAME)
    reply_channel, original_filename, temp_file_path, context = (
        command.reply_channel,
        command.original_filename,
        command.temp_file_path,
        command.context,
    )
    if not isinstance(temp_file_path, str) or not temp_file_path:
        raise StateError("Upload plugin command missing required temp_file_path.")
    user_id = context.user_id if context else 0
    task_id_value = resolve_upload_task_id(command)
    plugin_name, final_path, normalize_error = normalize_upload_target(manager, original_filename)
    upload_state = UploadExecutionState()
    try:
        async with manager.dependencies.infrastructure.lifecycle.lifecycle_scope(
            service_name="Plugin manager",
            task_type="upload_plugin",
            plugin_name=plugin_name,
            acquire_plugin_lock=True,
            user_id=user_id,
            task_id=task_id_value,
            context=context,
        ) as (task_token, task_id):
            registry = manager.dependencies.infrastructure.task_registry
            progress = create_task_progress_sender(
                reply_channel,
                task_id,
                registry,
                manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
            )
            try:
                if await reject_upload_preflight_if_needed(
                    manager=manager,
                    logger=logger,
                    reply_channel=reply_channel,
                    task_id=task_id,
                    registry=registry,
                    original_filename=original_filename,
                    normalize_error=normalize_error,
                    send_completion_with_task=send_completion_with_task,
                ):
                    return
                if not plugin_name or not final_path:
                    raise StateError(
                        "Upload plugin internal error: missing resolved plugin_name or final_path.",
                    )
                outcome = await perform_plugin_upload_steps(
                    manager,
                    progress=progress,
                    task_token=task_token,
                    state=upload_state,
                    plugin_name=plugin_name,
                    final_path=final_path,
                    temp_file_path=temp_file_path,
                    context=context,
                )
                display_name = await manager.get_plugin_display_name(plugin_name)
                if outcome.disposition is UploadedPluginDisposition.RETAINED_INCOMPATIBLE:
                    message = (
                        f"Plugin '{display_name}' uploaded successfully. "
                        "It is incompatible with this system and remains disabled."
                    )
                else:
                    message = f"Plugin '{display_name}' uploaded and loaded successfully."
                if outcome.requires_backend_installation:
                    message += " This plugin requires a backend installation."
                await uncancel_then_cleanup(
                    send_success_completion_for_plugin_manager(
                        manager,
                        reply_channel,
                        task_id,
                        message,
                    )
                )
            except (
                asyncio.CancelledError,
                TaskCancelledError,
                MoveFileCommittedAfterCancellationError,
            ) as exception:
                logger.info(
                    "Upload of plugin '%s' cancelled: %s",
                    plugin_name,
                    str(exception) or "user request",
                )
                committed_path = (
                    exception.destination_path or final_path
                    if isinstance(exception, MoveFileCommittedAfterCancellationError)
                    else final_path if upload_state.file_moved else None
                )
                await uncancel_then_cleanup(
                    rollback_plugin_upload(
                        manager,
                        state=upload_state,
                        plugin_name=plugin_name,
                        final_path=final_path,
                        committed_path=committed_path,
                        logger=logger,
                    )
                )
                await uncancel_then_cleanup(
                    notify_operation_cancelled(
                        "Plugin upload",
                        reply_channel,
                        task_id,
                        registry,
                        manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                    )
                )
            except HANDLED_RUNTIME_EXCEPTIONS as exception:
                if isinstance(exception, ValueError):
                    log_handled_exception(
                        logger,
                        exception,
                        message=f"Blocked upload of plugin '{original_filename}'.",
                        operation=OPERATION,
                        details={"filename": original_filename},
                    )
                else:
                    log_exception(
                        logger,
                        exception,
                        message="Failed to upload plugin",
                        operation=OPERATION,
                        details={"filename": original_filename},
                    )
                await uncancel_then_cleanup(
                    rollback_plugin_upload(
                        manager,
                        state=upload_state,
                        plugin_name=plugin_name,
                        final_path=final_path,
                        committed_path=(final_path if upload_state.file_moved else None),
                        logger=logger,
                    )
                )
                await uncancel_then_cleanup(
                    send_completion_with_task(
                        reply_channel,
                        task_id,
                        success=False,
                        message=resolve_upload_failure_message(exception),
                        error_code=resolve_upload_failure_code(exception),
                        task_registry=registry,
                        send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                    )
                )
    except TaskIDCollisionError as exception:
        await handle_upload_task_id_collision(
            manager,
            exception,
            reply_channel=reply_channel,
            placeholder_created=upload_state.placeholder_created,
            plugin_name=plugin_name,
            final_path=final_path,
        )
    finally:
        staged_file_cleanup = async_remove_if_exists(
            temp_file_path,
            logger=logger,
            log_level=logging.DEBUG,
        )
        await uncancel_then_cleanup(staged_file_cleanup)
