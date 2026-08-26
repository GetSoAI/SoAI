"""SoAI - File content streaming helpers [backend/files/streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.concurrency.cancellation_cleanup import shielded_cleanup
from core.concurrency.queue_backpressure import (
    BackpressureDeliveryStatus,
    put_with_backpressure,
)
from core.concurrency.queue_ops import (
    QueueDropTracker,
    log_queue_drop_with_tracker,
    put_nowait_with_overwrite,
)
from core.concurrency.queue_race import (
    QueueRaceOutcome,
    race_queue_operation_against_signals,
)
from core.config.byte_sizes import MIB_BYTES
from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import NotFoundError, StateError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_files import FileContentQuery
from core.events.types_models_streaming import StreamChunkEvent, StreamEndEvent
from core.events.types_plugins import ErrorEvent
from core.files.managed_storage_errors import FileStorageSecurityError
from core.files.managed_storage_traversal import normalize_storage_relative_path
from core.files.protocols import DatabaseFilesProtocol
from core.filesystem.async_queries import async_isfile
from core.filesystem.async_read import async_read_managed_file_chunks
from core.logging.trace import get_logger
from core.tasks.asyncio_task_spawner import create_tracked_task
from core.tasks.cancellation_id import require_command_cancellation_id
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskCancellationBinderProtocol, TaskRegistryProtocol
from core.timing.constants import CONTROL_TIMEOUT_SEC, INTERACTIVE_TIMEOUT_SEC

__all__ = ("stream_file_content",)

LOGGER_NAME = "SoAI.files.streaming"
OPERATION_FILE_MANAGER_HANDLE_FILE_CONTENT_QUERY = "file_manager.handle_file_content_query"
OPERATION_FILE_MANAGER_HANDLE_FILE_CONTENT_QUERY_CANCELLED_FINALIZE = (
    "file_manager.handle_file_content_query.cancelled.finalize"
)


_FILE_STREAM_CHUNK_SIZE_BYTES = MIB_BYTES
_FILE_STREAM_DROP_WARNING_INTERVAL_SECONDS: float = 30.0
_FILE_STREAM_OWNED_FAILURES: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    FileStorageSecurityError,
    OSError,
)


async def stream_file_content(
    command: FileContentQuery,
    *,
    storage_root: str,
    database_files: DatabaseFilesProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    task_registry: TaskRegistryProtocol,
    shutdown_event: asyncio.Event,
) -> None:
    reply_channel = command.reply_channel
    file_id_raw = command.payload.get("file_id")
    if not isinstance(file_id_raw, str) or not file_id_raw.strip():
        raise ValidationError("file_id must be a non-empty string.")
    file_id = file_id_raw.strip()
    try:
        command_context = command.context
    except AttributeError:
        command_context = None
    if command_context is None:
        task_id = None
    else:
        try:
            task_id = command_context.task_id
        except AttributeError:
            task_id = None
    file_info = await database_files.get_file_info_with_path(
        file_id,
        enforce_owner=True,
        user_id=command.user_id,
        api_key_id=command.api_key_id,
    )
    file_path = file_info.get("file_path") if file_info else None
    if not file_path:
        raise NotFoundError(f"File ID '{file_id}' not found.")
    parts = normalize_storage_relative_path(storage_root, file_path)
    safe_path = os.path.join(storage_root, *parts)
    if not await async_isfile(safe_path):
        await database_files.delete_file(
            file_id,
            enforce_owner=True,
            user_id=command.user_id,
            api_key_id=command.api_key_id,
        )
        raise NotFoundError(
            f"File ID '{file_id}' found in database but missing from storage. The record has been cleaned up.",
        )
    cancellation_id = require_command_cancellation_id(command)
    logger = get_logger(LOGGER_NAME)

    async def _stream_file_async() -> None:
        drop_tracker = QueueDropTracker(_FILE_STREAM_DROP_WARNING_INTERVAL_SECONDS)
        terminal_event: StreamEndEvent | ErrorEvent | None = None

        async def deliver_file_event(event: StreamEndEvent | ErrorEvent, description: str) -> None:
            overwrite_result = put_nowait_with_overwrite(reply_channel, event, overwrite_attempts=1)
            if overwrite_result.delivered:
                return
            result = await race_queue_operation_against_signals(
                reply_channel.put(event),
                (shutdown_event,),
                timeout_seconds=None,
            )
            if result.outcome == QueueRaceOutcome.SIGNAL_FIRED:
                logger.debug("%s not delivered due to shutdown.", type(event).__name__)
                return
            if result.outcome != QueueRaceOutcome.OPERATION_COMPLETED:
                raise StateError(description)

        try:
            if shutdown_event.is_set():
                return
            file_chunk_iterator = async_read_managed_file_chunks(
                storage_root,
                file_path,
                chunk_size=_FILE_STREAM_CHUNK_SIZE_BYTES,
                read_timeout_sec=INTERACTIVE_TIMEOUT_SEC,
                shutdown_event=shutdown_event,
            )
            async for chunk in file_chunk_iterator:
                delivery = await put_with_backpressure(
                    reply_channel,
                    StreamChunkEvent(chunk=chunk),
                    shutdown_event,
                    backpressure_timeout=CONTROL_TIMEOUT_SEC,
                )
                if delivery.status == BackpressureDeliveryStatus.SHUTDOWN:
                    return
                if delivery.status == BackpressureDeliveryStatus.TIMEOUT:
                    log_queue_drop_with_tracker(
                        logger,
                        drop_tracker,
                        max(1, delivery.dropped_count),
                        f"File stream for {file_id} stalled due to backpressure",
                    )
                    terminal_event = ErrorEvent(
                        message="File stream stalled due to backpressure.",
                        error_type=ErrorType.SERVER_ERROR,
                        context=command_context,
                    )
                    if isinstance(task_id, str) and task_id:
                        await finalize(
                            task_registry,
                            task_id,
                            TaskStatus.FAILED,
                            error_code=504,
                            error_message="File stream stalled due to backpressure.",
                            status_message="File stream stalled",
                            emit_reply_completion_event=False,
                        )
                    return
            if isinstance(task_id, str) and task_id:
                await finalize(
                    task_registry,
                    task_id,
                    TaskStatus.COMPLETED,
                    result={"file_id": file_id},
                    status_message="File content stream completed",
                    emit_reply_completion_event=False,
                )
            terminal_event = StreamEndEvent()
        except _FILE_STREAM_OWNED_FAILURES as exception:
            log_exception(
                logger,
                exception,
                message="Error during file content streaming",
                operation=OPERATION_FILE_MANAGER_HANDLE_FILE_CONTENT_QUERY,
                details={"file_id": file_id},
            )
            terminal_event = ErrorEvent(
                message="File content streaming failed.",
                error_type=ErrorType.SERVER_ERROR,
                context=command_context,
            )
            if isinstance(task_id, str) and task_id:
                await finalize(
                    task_registry,
                    task_id,
                    TaskStatus.FAILED,
                    error_code=500,
                    error_message="File content streaming failed.",
                    emit_reply_completion_event=False,
                )
        except asyncio.CancelledError:
            if isinstance(task_id, str) and task_id:
                cancel_reason = "Client disconnected."
                try:
                    await shielded_cleanup(
                        finalize(
                            task_registry,
                            task_id,
                            TaskStatus.CANCELLED,
                            error_message=cancel_reason,
                            status_message=cancel_reason,
                            emit_reply_completion_event=False,
                        ),
                    )
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Failed to finalize cancelled file content stream task (non-critical).",
                        operation=OPERATION_FILE_MANAGER_HANDLE_FILE_CONTENT_QUERY_CANCELLED_FINALIZE,
                        details={"file_id": file_id, "task_id": task_id},
                        level="debug",
                    )
            raise
        finally:
            if isinstance(terminal_event, ErrorEvent):
                await deliver_file_event(
                    terminal_event,
                    f"Failed to deliver file stream error event for {file_id} due to reply channel backpressure",
                )
            elif isinstance(terminal_event, StreamEndEvent):
                await deliver_file_event(
                    terminal_event,
                    f"Failed to deliver StreamEndEvent for {file_id} due to reply channel backpressure",
                )

    _ = await create_tracked_task(
        _stream_file_async(),
        cancellation_binder=cancellation_binder,
        cancellation_id=cancellation_id,
        owner="file_content_stream",
        name=f"file-manager-stream-{file_id}",
        logger=logger,
        metadata={"file_id": file_id},
    )
