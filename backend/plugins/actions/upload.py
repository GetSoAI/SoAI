"""SoAI - Plugin upload task handler with validation and installation [backend/plugins/actions/upload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SecurityError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_plugins import UploadPluginCommand
from core.files.move_with_cancellation import (
    MoveFileCommittedAfterCancellationError,
)
from core.files.operations import async_remove_if_exists
from core.logging.trace import get_logger
from core.plugins.errors import PluginIncompatibleError
from core.tasks.errors import TaskIDCollisionError
from plugins.actions.progress import (
    create_task_progress_sender,
    notify_operation_cancelled,
    send_completion_with_task,
    send_success_completion_for_plugin_manager,
)
from plugins.actions.upload_cleanup import (
    UploadExecutionState,
    cleanup_created_upload_runtime,
)
from plugins.actions.upload_placeholder_cleanup import cleanup_uploading_placeholder
from plugins.actions.upload_steps import perform_plugin_upload_steps
from plugins.actions.upload_task_collision import handle_upload_task_id_collision
from plugins.actions.upload_validation import (
    normalize_upload_target,
    reject_upload_preflight_if_needed,
    resolve_upload_failure_code,
    resolve_upload_task_id,
    safe_remove_upload_file,
)

if TYPE_CHECKING:
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ()

LOGGER_NAME = "SoAI.plugins.actions.upload"
OPERATION = "plugin_flow.process_upload_plugin_async"
PLUGIN_UPLOAD_FAILURE_EXCEPTIONS = RECOVERABLE_EXCEPTIONS + (
    PluginIncompatibleError,
    SecurityError,
    StateError,
    ValidationError,
    ValueError,
)


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
                requires_backend_install = await perform_plugin_upload_steps(
                    manager,
                    progress=progress,
                    task_token=task_token,
                    state=upload_state,
                    plugin_name=plugin_name,
                    final_path=final_path,
                    temp_file_path=temp_file_path,
                    context=context,
                )
                message = f"Plugin '{await manager.get_plugin_display_name(plugin_name)}' uploaded and loaded successfully."
                if requires_backend_install:
                    message += " This plugin requires a backend installation."
                await send_success_completion_for_plugin_manager(
                    manager,
                    reply_channel,
                    task_id,
                    message,
                )
            except asyncio.CancelledError:
                logger.info("Upload of plugin '%s' cancelled by user request.", plugin_name)
                if upload_state.file_moved:
                    await safe_remove_upload_file(final_path, logger=logger)
                    await cleanup_created_upload_runtime(
                        manager,
                        state=upload_state,
                        plugin_name=plugin_name,
                        logger=logger,
                    )
                await notify_operation_cancelled(
                    "Plugin upload",
                    reply_channel,
                    task_id,
                    registry,
                    manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                )
                await cleanup_uploading_placeholder(
                    manager,
                    placeholder_created=upload_state.placeholder_created,
                    plugin_name=plugin_name,
                    final_path=final_path,
                )
            except (TaskCancelledError, MoveFileCommittedAfterCancellationError) as exception:
                logger.info(
                    "Upload of plugin '%s' cancelled: %s",
                    plugin_name,
                    str(exception),
                )
                cleanup_path = final_path
                if isinstance(exception, MoveFileCommittedAfterCancellationError):
                    cleanup_path = exception.destination_path or final_path
                await safe_remove_upload_file(cleanup_path, logger=logger)
                await cleanup_created_upload_runtime(
                    manager,
                    state=upload_state,
                    plugin_name=plugin_name,
                    logger=logger,
                )
                await notify_operation_cancelled(
                    "Plugin upload",
                    reply_channel,
                    task_id,
                    registry,
                    manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                )
                await cleanup_uploading_placeholder(
                    manager,
                    placeholder_created=upload_state.placeholder_created,
                    plugin_name=plugin_name,
                    final_path=final_path,
                )
            except PLUGIN_UPLOAD_FAILURE_EXCEPTIONS as exception:
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
                if upload_state.file_moved and final_path is not None:
                    await safe_remove_upload_file(final_path, logger=logger)
                    await cleanup_created_upload_runtime(
                        manager,
                        state=upload_state,
                        plugin_name=plugin_name,
                        logger=logger,
                    )
                failure_code = resolve_upload_failure_code(exception)
                await send_completion_with_task(
                    reply_channel,
                    task_id,
                    success=False,
                    message=str(exception),
                    error_code=failure_code,
                    task_registry=registry,
                    send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
                )
                await cleanup_uploading_placeholder(
                    manager,
                    placeholder_created=upload_state.placeholder_created,
                    plugin_name=plugin_name,
                    final_path=final_path,
                )
            finally:
                if temp_file_path:
                    await async_remove_if_exists(
                        temp_file_path,
                        logger=logger,
                        log_level=logging.DEBUG,
                    )
    except TaskIDCollisionError as exception:
        await handle_upload_task_id_collision(
            manager,
            exception,
            reply_channel=reply_channel,
            context=context,
            temp_file_path=temp_file_path,
            placeholder_created=upload_state.placeholder_created,
            plugin_name=plugin_name,
            final_path=final_path,
        )
