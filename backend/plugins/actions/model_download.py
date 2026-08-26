"""SoAI - Model download request handling and progress tracking [backend/plugins/actions/model_download.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.cancellation import create_cancellation_watch_task
from core.concurrency.protocols import CancellationTokenProtocol
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import InsufficientDiskSpaceError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_models_model_commands import ModelDownloadCommand
from core.logging.trace import get_logger
from core.progress.transfer_details import resolve_transfer_progress_details
from core.tasks.cancel_watcher import cleanup_cancel_watcher
from core.tasks.errors import TaskIDCollisionError
from plugins.actions.model_download_runner import run_plugin_download
from plugins.actions.model_download_stats import (
    parse_download_stats,
    record_download_speed,
)
from plugins.actions.model_download_validation import (
    check_offline_mode_blocks_download,
    validate_plugin_for_download,
)
from plugins.actions.progress import (
    notify_operation_cancelled,
    send_completion_with_task,
    send_progress_with_task,
    send_unexpected_error_completion_for_plugin_manager,
)
from plugins.manager.transfer_outcomes import ModelDiscoveryQueueStatus
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)
from plugins.state.progress import PhaseAwareProgressMapper
from plugins.state.task_collisions import handle_plugin_manager_task_id_collision

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.types.json import JSONDict

__all__ = ("process_model_download_async",)

LOGGER_NAME = "SoAI.plugins.actions.model_download"
OPERATION_PLUGIN_ACTIONS_PROCESS_MODEL_DOWNLOAD_ASYNC = (
    "plugin_actions.process_model_download_async"
)
OPERATION_PLUGIN_FLOW_PROCESS_MODEL_DOWNLOAD_ASYNC = "plugin_flow.process_model_download_async"


async def process_model_download_async(
    manager: PluginManagerRuntimeProtocol,
    command: ModelDownloadCommand,
) -> None:
    plugin_name, reply_channel, context = (
        command.plugin_name,
        command.reply_channel,
        command.context,
    )
    display_name = await manager.get_plugin_display_name(plugin_name)
    metadata: JSONDict = {"model_id": command.model_id}
    if command.quantization:
        metadata["quantization"] = command.quantization
    user_id = context.user_id if context else 0
    try:
        if context is not None:
            try:
                existing_task_id = context.task_id
            except AttributeError:
                existing_task_id = None
        else:
            existing_task_id = None
        async with manager.dependencies.infrastructure.lifecycle.lifecycle_scope(
            service_name="Plugin manager",
            task_type="model_download",
            plugin_name=plugin_name,
            metadata=metadata,
            acquire_plugin_lock=True,
            user_id=user_id,
            task_id=existing_task_id,
            context=context,
        ) as (token, task_id):
            await _execute_download_within_scope(
                manager,
                command,
                display_name,
                reply_channel,
                token,
                task_id,
            )
    except TaskIDCollisionError as exception:
        await handle_plugin_manager_task_id_collision(manager, exception, reply_channel)


async def _execute_download_within_scope(
    manager: PluginManagerRuntimeProtocol,
    command: ModelDownloadCommand,
    display_name: str,
    reply_channel: asyncio.Queue[Event],
    token: CancellationTokenProtocol,
    task_id: str | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    phase_mapper = PhaseAwareProgressMapper(
        phase_ranges={"setup": (0, 10), "download": (10, 95), "finalize": (95, 100)},
    )

    async def stream_cb(data: JSONDict) -> None:
        percent_value = phase_mapper.process_callback(data)
        message_value = data.get("message", "")
        message_str = message_value if isinstance(message_value, str) else ""
        details_value = resolve_transfer_progress_details(data, data.get("details"))
        details_str = details_value if isinstance(details_value, str) else ""
        await send_progress_with_task(
            reply_channel,
            task_id,
            percent_value,
            message_str,
            manager.dependencies.infrastructure.task_registry,
            manager.dependencies.infrastructure.task_helpers.send_task_progress_event,
            details=details_str,
        )

    download_registered = False
    per_task_shutdown_event = asyncio.Event()
    cancel_watcher: asyncio.Task[None] | None = None
    try:
        if await check_offline_mode_blocks_download(reply_channel, task_id, manager):
            return
        validated = await validate_plugin_for_download(
            manager,
            command.plugin_name,
            display_name,
            reply_channel,
            task_id,
        )
        if not validated:
            return
        await stream_cb(
            {
                "message": f"Starting download of '{command.model_id}' via '{display_name}' plugin..."
            },
        )
        await manager.register_model_download(command.plugin_name)
        download_registered = True
        cancel_watcher = create_cancellation_watch_task(
            token,
            per_task_shutdown_event,
            name=f"plugin-download-cancel-watch-{task_id or command.plugin_name}",
        )
        success, message, download_stats = await run_plugin_download(
            validated.plugin_instance,
            command,
            per_task_shutdown_event,
            stream_cb,
        )
        if success:
            await stream_cb({"message": "Download complete. Queuing model discovery..."})
            stats = parse_download_stats(download_stats)
            await record_download_speed(manager, command.plugin_name, command.model_id, stats)
        finalization = await manager.finalize_model_download(
            command.plugin_name,
            context=command.context,
            discovery_requested=success,
        )
        if success:
            logger.info(
                "Model '%s' downloaded successfully via '%s'.",
                command.model_id,
                display_name,
            )
        completion_message = message or f"Model download {'succeeded' if success else 'failed'}."
        completion_result: JSONDict | None = None
        if success:
            completion_result = {
                "model_id": command.model_id,
                "discovery_status": finalization.discovery_status.value,
            }
            if finalization.discovery_status is ModelDiscoveryQueueStatus.DEFERRED:
                completion_message = f"{completion_message} Model discovery was deferred and will retry automatically."
        await send_completion_with_task(
            reply_channel,
            task_id,
            success=success,
            message=completion_message,
            result=completion_result,
            task_registry=manager.dependencies.infrastructure.task_registry,
            send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
        )
    except asyncio.CancelledError:
        await _handle_download_cancellation(
            manager,
            command,
            display_name,
            download_registered,
            per_task_shutdown_event,
            reply_channel,
            task_id,
        )
        raise
    except InsufficientDiskSpaceError as exception:
        if download_registered:
            await manager.finalize_model_download(
                command.plugin_name,
                context=command.context,
                discovery_requested=False,
            )
        log_handled_exception(
            logger,
            exception,
            message=str(exception.message),
            operation=OPERATION_PLUGIN_ACTIONS_PROCESS_MODEL_DOWNLOAD_ASYNC,
            details={
                "model_id": command.model_id,
                "plugin": display_name,
                **dict(exception.details or {}),
            },
            level="warning",
        )
        await send_completion_with_task(
            reply_channel,
            task_id,
            success=False,
            message=str(exception.message),
            error_code=507,
            error_message=str(exception.message),
            task_registry=manager.dependencies.infrastructure.task_registry,
            send_task_complete_event_callable=manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        if download_registered:
            await manager.finalize_model_download(
                command.plugin_name,
                context=command.context,
                discovery_requested=False,
            )
        log_exception(
            logger,
            exception,
            message="Error during model download",
            operation=OPERATION_PLUGIN_FLOW_PROCESS_MODEL_DOWNLOAD_ASYNC,
            details={"model_id": command.model_id, "plugin": display_name},
        )
        await send_unexpected_error_completion_for_plugin_manager(
            manager,
            reply_channel,
            task_id,
            exception,
        )
    finally:
        await cleanup_cancel_watcher(
            cancel_watcher,
            operation="plugin_flow.process_model_download_async.cancel_watcher_cleanup",
            logger=get_logger(LOGGER_NAME),
            details={"model_id": command.model_id, "plugin": display_name},
            error_level="warning",
        )


async def _handle_download_cancellation(
    manager: PluginManagerRuntimeProtocol,
    command: ModelDownloadCommand,
    display_name: str,
    download_registered: bool,
    shutdown_event: asyncio.Event,
    reply_channel: asyncio.Queue[Event],
    task_id: str | None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if download_registered:
        shutdown_event.set()
        await manager.finalize_model_download(
            command.plugin_name,
            context=command.context,
            discovery_requested=False,
        )
    logger.info(
        "Model download for '%s' via '%s' was cancelled.",
        command.model_id,
        display_name,
    )
    await notify_operation_cancelled(
        "Model download",
        reply_channel,
        task_id,
        manager.dependencies.infrastructure.task_registry,
        manager.dependencies.infrastructure.task_helpers.send_task_complete_event,
    )
