"""SoAI - Streaming upload exception handling shared logic [backend/features/api/routes/file_explorer/upload_transfer/streaming/exception_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    ApiError,
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tasks.enums import TaskStatus
from features.api.routes.file_explorer.upload_transfer_failure_finalization import (
    finalize_and_raise_payload_too_large,
    finalize_and_raise_validation_error,
)
from features.api.runtime.task_api_errors import (
    raise_api_error_with_task,
    raise_disk_space_api_error,
)
from features.api.runtime.task_execution import (
    finalize_task_safely,
)

if TYPE_CHECKING:
    from fastapi import Request

    from core.logging.protocols import TraceLogger
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONValue
    from features.api.routes.file_explorer.upload_transfer_task_context import (
        UploadTaskContext,
    )

__all__ = (
    "StreamingUploadErrorPolicy",
    "handle_streaming_upload_exception",
)


@dataclass(frozen=True, slots=True)
class StreamingUploadErrorPolicy:
    logger: TraceLogger
    payload_too_large_finalize_operation: str
    validation_finalize_operation: str
    cancelled_finalize_operation: str
    failed_finalize_operation: str
    disk_space_operation: str
    recoverable_log_message: str
    recoverable_server_error_message: str
    cancelled_user_message: str


async def handle_streaming_upload_exception(
    request: Request,
    *,
    exception: BaseException,
    registry: TaskRegistryProtocol,
    task_context: UploadTaskContext,
    policy: StreamingUploadErrorPolicy,
    operation: str,
    cleanup_on_task_cancel: Callable[[], Awaitable[None]],
    cancel_disconnect_action: Callable[[], Awaitable[None]],
    recoverable_log_details: dict[str, JSONValue],
    recoverable_disk_space_details: dict[str, JSONValue],
    cancel_cleanup: Callable[[], Awaitable[None]] | None,
    cancel_use_uncancel: bool,
) -> NoReturn:
    if isinstance(exception, PayloadTooLargeError):
        await finalize_and_raise_payload_too_large(
            request,
            registry=registry,
            task_id=task_context.task_id,
            trace_id=task_context.trace_id,
            operation=policy.payload_too_large_finalize_operation,
            exception=exception,
        )
    if isinstance(exception, ValidationError):
        await finalize_and_raise_validation_error(
            request,
            registry=registry,
            task_id=task_context.task_id,
            trace_id=task_context.trace_id,
            operation=policy.validation_finalize_operation,
            exception=exception,
        )
    if isinstance(exception, TaskCancelledError):
        await cleanup_on_task_cancel()
        await finalize_task_safely(
            registry=registry,
            task_id=task_context.task_id,
            status=TaskStatus.CANCELLED,
            trace_id=task_context.trace_id,
            operation=policy.cancelled_finalize_operation,
            error_message=str(exception),
            status_message=str(exception),
        )
        raise_api_error_with_task(
            request,
            499,
            "cancelled",
            policy.cancelled_user_message,
            task_id=task_context.task_id,
        )
    if isinstance(exception, asyncio.CancelledError):
        if cancel_use_uncancel:
            await uncancel_then_cleanup(cancel_disconnect_action())
            if cancel_cleanup is not None:
                await uncancel_then_cleanup(cancel_cleanup())
        else:
            await cancel_disconnect_action()
        raise exception
    if isinstance(exception, InsufficientDiskSpaceError):
        await raise_disk_space_api_error(
            request=request,
            exception=exception,
            operation=policy.disk_space_operation,
            trace_id=task_context.trace_id,
            registry=registry,
            task_id=task_context.task_id,
            details=recoverable_disk_space_details,
        )
    if isinstance(exception, ApiError):
        await finalize_task_safely(
            registry=registry,
            task_id=task_context.task_id,
            status=TaskStatus.FAILED,
            trace_id=task_context.trace_id,
            operation=policy.failed_finalize_operation,
            error_code=exception.http_status,
            error_message=exception.message,
            status_message=exception.message,
        )
        raise exception
    if isinstance(exception, RECOVERABLE_EXCEPTIONS):
        await finalize_task_safely(
            registry=registry,
            task_id=task_context.task_id,
            status=TaskStatus.FAILED,
            trace_id=task_context.trace_id,
            operation=policy.failed_finalize_operation,
            error_code=500,
            error_message=str(exception),
            status_message="Upload failed",
        )
        log_exception(
            policy.logger,
            exception,
            message=policy.recoverable_log_message,
            operation=operation,
            trace_id=task_context.trace_id,
            details=recoverable_log_details,
            level="warning",
        )
        raise_api_error_with_task(
            request,
            500,
            "server_error",
            policy.recoverable_server_error_message,
            task_id=task_context.task_id,
        )
    raise exception
