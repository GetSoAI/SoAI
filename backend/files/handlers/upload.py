"""SoAI - File upload command handler [backend/files/handlers/upload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.errors.error_types import ErrorType
from core.errors.exception_logging import log_exception
from core.errors.exceptions import InsufficientDiskSpaceError, ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_files import FileStatus, FileUploadCommand
from core.events.types_models_streaming import InferenceResultEvent
from core.files.move_with_cancellation import (
    MoveFileCommittedAfterCancellationError,
    move_file_with_cancellation,
)
from core.files.operations import secure_filename
from core.files.protocols import DatabaseFilesProtocol
from core.files.upload_cleanup import cleanup_upload_artifacts
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
) -> None:
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
    storage_manager: StorageManagerProtocol,
    token_collection: TokenCollectionProtocol,
    cancellation_history: CancellationHistoryProtocol,
    cancellation_event_bus: CancellationEventBusProtocol,
    task_registry: TaskRegistryProtocol,
) -> None:
    logger = get_logger(LOGGER_NAME)
    permanent_filepath: str | None = None
    database_record_created = False
    try:
        safe_filename = secure_filename(command.original_filename)
        if not safe_filename:
            raise ValidationError(
                "Provided filename is invalid or results in an empty string after sanitization.",
            )
        cancellation_id = require_command_cancellation_id(command)
        file_id = f"file-{uuid.uuid4().hex}"
        permanent_filename = f"{file_id}_{safe_filename}"
        permanent_filepath = os.path.join(storage_root, permanent_filename)
        temp_file_size = int(os.stat(command.temp_file_path).st_size)
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
                    )
            token.raise_if_cancelled()
            file_stats = await asyncio.to_thread(os.stat, permanent_filepath)
            token.raise_if_cancelled()
            created_at_ms = int(epoch_ms())
            created_at = ms_to_seconds_floor(created_at_ms)
            status = FileStatus.UPLOADED.value
            await database_files.add_file(
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
            )
            database_record_created = True
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
        logger.info(
            "File upload for '%s' cancelled after destination commit.",
            command.original_filename,
        )
        await _send_cancellation_complete_reply(
            command.reply_channel,
            registry=task_registry,
            logger=logger,
            filename=command.original_filename,
            message=str(exception) or "File upload cancelled.",
        )
        await cleanup_upload_artifacts(
            temp_path=command.temp_file_path,
            permanent_path=exception.destination_path,
            log_level=logging.DEBUG,
        )
    except TaskCancelledError as exception:
        logger.info(
            "File upload for '%s' cancelled: %s",
            command.original_filename,
            str(exception),
        )
        await _send_cancellation_complete_reply(
            command.reply_channel,
            registry=task_registry,
            logger=logger,
            filename=command.original_filename,
            message=str(exception) or "File upload cancelled.",
        )
        await cleanup_upload_artifacts(
            temp_path=command.temp_file_path,
            permanent_path=None if database_record_created else permanent_filepath,
            log_level=logging.DEBUG,
        )
    except asyncio.CancelledError:
        logger.info(
            "File upload for '%s' cancelled by user request.",
            command.original_filename,
        )
        await _send_cancellation_complete_reply(
            command.reply_channel,
            registry=task_registry,
            logger=logger,
            filename=command.original_filename,
            message="File upload cancelled.",
        )
        await cleanup_upload_artifacts(
            temp_path=command.temp_file_path,
            permanent_path=None if database_record_created else permanent_filepath,
            log_level=logging.DEBUG,
        )
        raise
    except InsufficientDiskSpaceError as exception:
        log_exception(
            logger=logger,
            exception=exception,
            message="File upload failed due to insufficient disk space",
            operation=OPERATION,
            details={"filename": command.original_filename},
        )
        await send_error_event_and_finalize(
            command.reply_channel,
            str(exception.message),
            ErrorType.UPLOAD_ERROR,
            registry=task_registry,
        )
        await cleanup_upload_artifacts(
            temp_path=command.temp_file_path,
            permanent_path=None if database_record_created else permanent_filepath,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger=logger,
            exception=exception,
            message="File upload failed",
            operation=OPERATION,
            details={"filename": command.original_filename},
        )
        await send_error_event_and_finalize(
            command.reply_channel,
            str(exception),
            ErrorType.SERVER_ERROR,
            registry=task_registry,
        )
        await cleanup_upload_artifacts(
            temp_path=command.temp_file_path,
            permanent_path=None if database_record_created else permanent_filepath,
        )
