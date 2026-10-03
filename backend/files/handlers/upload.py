"""SoAI - File upload command handler [backend/files/handlers/upload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import uuid
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import (
    run_idempotent_current_task_operation,
)
from core.database.protocols import DatabaseOperationStatusProtocol
from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.exceptions import InsufficientDiskSpaceError, SoAIError, ValidationError
from core.errors.public_projection import project_public_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_files import FileStatus, FileUploadCommand
from core.events.types_models_streaming import InferenceResultEvent
from core.files.generated_names import generated_upload_filename
from core.files.move_errors import MoveFileCommittedError
from core.files.move_with_cancellation import (
    MoveFileCommittedAfterCancellationError,
    move_file_with_cancellation,
)
from core.files.operations import secure_filename
from core.files.protocols import DatabaseFilesProtocol
from core.filesystem.path_coercion import normalize_filesystem_path
from core.hardware.reservation_claims import claim_reserved_write
from core.logging.protocols import StandardLogger
from core.logging.trace import get_logger
from core.tasks.api_events import send_task_complete_event
from core.tasks.cancellation_id import require_command_cancellation_id
from core.tasks.cancellation_token_scope import cancellation_token_scope
from core.tasks.failure_events import send_error_event_and_finalize
from core.tasks.protocols import (
    CancellationEventBusProtocol,
    CancellationHistoryProtocol,
    TaskRegistryProtocol,
    TokenCollectionProtocol,
)
from core.timing.durations import ms_to_seconds_floor
from core.timing.epoch import epoch_ms
from files.formatting import format_openai_file_object
from files.handlers.response import deliver_reply_event_with_warnings
from files.upload_acceptance import UploadAcceptance

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.types.json import JSONDict

__all__ = ("handle_file_upload",)

LOGGER_NAME = "SoAI.files.handlers.upload"
OPERATION = "files.handlers.upload.handle_file_upload"


async def _send_cancellation_complete_reply(
    reply_channel: asyncio.Queue[Event],
    *,
    registry: TaskRegistryProtocol,
    logger: StandardLogger,
    filename: str,
    message: str,
    overwrite_attempts: int = 2,
    acceptance_error: SoAIError | None = None,
) -> None:
    if acceptance_error is not None:
        log_exception(
            logger,
            acceptance_error,
            message="Upload completion remains unresolved.",
            operation=OPERATION,
        )
        await send_error_event_and_finalize(
            reply_channel,
            project_public_exception(acceptance_error).message,
            ErrorType.SERVER_ERROR,
            registry=registry,
        )
        return
    completion_event = await send_task_complete_event(
        reply_channel,
        message,
        success=False,
        cancelled=True,
        registry=registry,
    )
    if completion_event is not None:
        if not deliver_reply_event_with_warnings(
            reply_channel,
            completion_event,
            operation=f"file upload cancellation for '{filename}'",
            overwrite_attempts=overwrite_attempts,
        ):
            logger.warning("Failed to deliver cancellation event for '%s'", filename)


async def handle_file_upload(
    command: FileUploadCommand,
    *,
    storage_root: str,
    database_files: DatabaseFilesProtocol,
    database_operation_status: DatabaseOperationStatusProtocol,
    storage_manager: StorageManagerProtocol,
    token_collection: TokenCollectionProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    task_registry: TaskRegistryProtocol,
) -> None:
    logger = get_logger(LOGGER_NAME)
    permanent_filepath: str | None = None
    acceptance = UploadAcceptance(
        database_files=database_files,
        database_operation_status=database_operation_status,
        temporary_path=command.temp_file_path,
        user_id=command.user_id,
        api_key_id=command.api_key_id,
    )
    try:
        safe_filename = secure_filename(command.original_filename)
        if not safe_filename:
            raise ValidationError(
                "Provided filename is invalid or results in an empty string after sanitization.",
            )
        cancellation_id = require_command_cancellation_id(command)
        file_id = f"file-{uuid.uuid4().hex}"
        permanent_filename = generated_upload_filename(file_id, safe_filename, storage_root)
        permanent_filepath = os.path.join(storage_root, permanent_filename)
        acceptance.file_id = file_id
        acceptance.permanent_path = permanent_filepath
        temp_file_size = int(os.stat(normalize_filesystem_path(command.temp_file_path)).st_size)
        async with cancellation_token_scope(
            token_collection,
            cancellation_history,
            cancellation_event_bus,
            cancellation_id=cancellation_id,
            owner="file_upload",
            metadata={"filename": safe_filename},
        ) as token:
            with storage_manager.reserve_disk_space(
                path=permanent_filepath,
                required_bytes=temp_file_size,
                operation="files.handlers.upload.handle_file_upload",
                details={
                    "purpose": "openai_file_upload_storage",
                    "filename": safe_filename,
                    "required_bytes": temp_file_size,
                },
            ) as reservation:
                with claim_reserved_write(reservation, size_bytes=temp_file_size):
                    await move_file_with_cancellation(
                        command.temp_file_path,
                        permanent_filepath,
                        token,
                        allow_overwrite=False,
                    )
                    acceptance.published = True
            token.raise_if_cancelled()
            file_stats = await asyncio.to_thread(
                os.stat, normalize_filesystem_path(permanent_filepath)
            )
            token.raise_if_cancelled()
            created_at_ms = int(epoch_ms())
            created_at = ms_to_seconds_floor(created_at_ms)
            status = FileStatus.UPLOADED.value
            acceptance.database_write_task = asyncio.create_task(
                database_files.add_file(
                    file_id=file_id,
                    filename=safe_filename,
                    purpose=command.purpose,
                    size_bytes=file_stats.st_size,
                    content_sha256=command.content_sha256,
                    created_at_ms=created_at_ms,
                    file_path=permanent_filepath,
                    user_id=command.user_id,
                    api_key_id=command.api_key_id,
                    status=status,
                    status_details=None,
                ),
                name="files.handlers.upload.accept",
            )
            await asyncio.shield(acceptance.database_write_task)
            acceptance.record_accepted = True
            response_payload: JSONDict = format_openai_file_object(
                {
                    "id": file_id,
                    "size_bytes": file_stats.st_size,
                    "created_at": created_at,
                    "filename": safe_filename,
                    "purpose": command.purpose,
                    "status": status,
                    "status_details": None,
                },
            )
            token.raise_if_cancelled()
            delivered = deliver_reply_event_with_warnings(
                command.reply_channel,
                InferenceResultEvent(payload=response_payload),
                operation=f"file upload response for '{safe_filename}'",
                overwrite_attempts=2,
            )
            if not delivered:
                await send_error_event_and_finalize(
                    command.reply_channel,
                    f"File upload completed but response delivery failed for '{safe_filename}'.",
                    ErrorType.SERVER_ERROR,
                    registry=task_registry,
                )
                return
    except MoveFileCommittedAfterCancellationError as exception:
        acceptance.published = True
        logger.info(
            "File upload for '%s' cancelled after destination commit.",
            command.original_filename,
        )
        cleanup_error = await run_idempotent_current_task_operation(
            acceptance.cleanup, restore_cancellation_requests=False
        )
        await _send_cancellation_complete_reply(
            command.reply_channel,
            registry=task_registry,
            acceptance_error=cleanup_error,
            logger=logger,
            filename=command.original_filename,
            message=str(exception) or "File upload cancelled.",
        )
    except TaskCancelledError as exception:
        logger.info(
            "File upload for '%s' cancelled: %s",
            command.original_filename,
            str(exception),
        )
        cleanup_error = await run_idempotent_current_task_operation(
            acceptance.cleanup, restore_cancellation_requests=False
        )
        await _send_cancellation_complete_reply(
            command.reply_channel,
            registry=task_registry,
            acceptance_error=cleanup_error,
            logger=logger,
            filename=command.original_filename,
            message=str(exception) or "File upload cancelled.",
        )
    except asyncio.CancelledError:
        logger.info(
            "File upload for '%s' cancelled by user request.",
            command.original_filename,
        )
        cleanup_error = await run_idempotent_current_task_operation(
            acceptance.cleanup, restore_cancellation_requests=False
        )
        await _send_cancellation_complete_reply(
            command.reply_channel,
            registry=task_registry,
            acceptance_error=cleanup_error,
            logger=logger,
            filename=command.original_filename,
            message="File upload cancelled.",
        )
        raise
    except InsufficientDiskSpaceError as exception:
        cleanup_error = await run_idempotent_current_task_operation(
            acceptance.cleanup, restore_cancellation_requests=False
        )
        log_exception(
            logger=logger,
            exception=cleanup_error or exception,
            message="File upload failed due to insufficient disk space",
            operation=OPERATION,
            details={"filename": command.original_filename},
        )
        await send_error_event_and_finalize(
            command.reply_channel,
            (
                project_public_exception(cleanup_error).message
                if cleanup_error is not None
                else str(exception.message)
            ),
            ErrorType.UPLOAD_ERROR,
            registry=task_registry,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        if isinstance(exception, MoveFileCommittedError):
            acceptance.published = True
        cleanup_error = await run_idempotent_current_task_operation(
            acceptance.cleanup, restore_cancellation_requests=False
        )
        log_exception(
            logger=logger,
            exception=cleanup_error or exception,
            message="File upload failed",
            operation=OPERATION,
            details={"filename": command.original_filename},
        )
        await send_error_event_and_finalize(
            command.reply_channel,
            project_public_exception(cleanup_error or exception).message,
            ErrorType.SERVER_ERROR,
            registry=task_registry,
        )
