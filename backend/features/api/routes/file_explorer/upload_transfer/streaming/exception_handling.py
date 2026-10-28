"""SoAI - Streaming upload exception handling shared logic [backend/features/api/routes/file_explorer/upload_transfer/streaming/exception_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, NoReturn

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    ApiError,
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    SecurityError,
    SoAIError,
    ValidationError,
)
from core.errors.public_projection import apply_public_error_payload, project_public_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.files.commit_receipt import (
    FileCleanupIncompleteError,
    FileCommitReceipt,
    FilePublicationUncertainError,
)
from core.files.move_with_cancellation import MoveFileCommittedAfterCancellationError
from core.filesystem.operation_errors import build_filesystem_operation_error
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

    from core.files.protocols_explorer import FileSystemRootScopeProtocol
    from core.logging.protocols import TraceLogger
    from core.tasks.protocols import TaskRegistryProtocol
    from core.types.json import JSONDict, JSONValue
    from features.api.routes.file_explorer.upload_transfer_task_context import (
        UploadTaskContext,
    )

__all__ = (
    "StreamingUploadErrorPolicy",
    "enrich_upload_publication_error",
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


def enrich_upload_publication_error(
    exception: (
        FilePublicationUncertainError
        | FileCleanupIncompleteError
        | MoveFileCommittedAfterCancellationError
    ),
    *,
    root_scope: FileSystemRootScopeProtocol,
    destination: str,
    receipts: list[FileCommitReceipt],
    details: JSONDict | None = None,
    append_destination_failure: bool = True,
) -> FilePublicationUncertainError | FileCleanupIncompleteError:
    failure = (
        exception
        if isinstance(exception, FilePublicationUncertainError | FileCleanupIncompleteError)
        else FilePublicationUncertainError(
            "The upload worker supplied no verified publication receipt.", cause=exception
        )
    )
    public_error = project_public_exception(failure)
    enriched: JSONDict = {**(public_error.details or {}), **(details or {})}
    results = details.get("results") if details is not None else None
    if isinstance(results, list) and append_destination_failure:
        enriched["results"] = [
            *results,
            {
                "path": root_scope.canonicalize_virtual_path(destination),
                "success": False,
                "error": public_error.message,
                "code": public_error.code,
            },
        ]
    diagnostics = failure.details or {}
    if diagnostics.get("cleanup_incomplete") is True:
        enriched["cleanup_incomplete"] = True
    if isinstance(failure, FilePublicationUncertainError):
        enriched["uncertain_paths"] = [root_scope.canonicalize_virtual_path(destination)]
    enriched["retained_paths"] = [
        root_scope.canonicalize_virtual_path(receipt.virtual_path) for receipt in receipts
    ]
    retained = diagnostics.get("retained_paths")
    if isinstance(retained, list):
        retained_virtual = enriched["retained_paths"]
        if isinstance(retained_virtual, list):
            for value in retained:
                if isinstance(value, str):
                    try:
                        retained_virtual.append(root_scope.to_virtual_path(value))
                    except SecurityError as projection_error:
                        failure.add_note(
                            f"Retained private entry cannot be projected: {projection_error}"
                        )
                        enriched["cleanup_incomplete"] = True
    apply_public_error_payload(failure, replace(public_error, details=enriched))
    return failure


async def handle_streaming_upload_exception(
    request: Request,
    *,
    exception: BaseException,
    registry: TaskRegistryProtocol,
    task_context: UploadTaskContext,
    policy: StreamingUploadErrorPolicy,
    operation: str,
    cleanup_on_task_cancel: Callable[[], Awaitable[list[str]]],
    cancel_disconnect_action: Callable[[], Awaitable[None]],
    recoverable_log_details: dict[str, JSONValue],
    recoverable_disk_space_details: dict[str, JSONValue],
    completed_result: JSONDict | None = None,
) -> NoReturn:
    if isinstance(exception, OSError):
        exception = build_filesystem_operation_error(exception, reference=task_context.trace_id)
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
    cancellation_details: JSONDict = (
        {
            "pre_cleanup_result": completed_result,
            "requested_total": completed_result["total"],
            "unattempted_paths": [],
        }
        if completed_result is not None
        else {}
    )
    if isinstance(exception, TaskCancelledError | asyncio.CancelledError):
        if isinstance(exception, TaskCancelledError):
            cancellation_details.update(project_public_exception(exception).details or {})
        elif isinstance(exception.__cause__, TaskCancelledError):
            cancellation_details.update(project_public_exception(exception.__cause__).details or {})
        try:
            removed_paths = await uncancel_then_cleanup(cleanup_on_task_cancel())
            cancellation_details.update({"removed_paths": removed_paths, "retained_paths": []})
        except HANDLED_RUNTIME_EXCEPTIONS as cleanup_error:
            if isinstance(cleanup_error, SoAIError):
                public_error = project_public_exception(cleanup_error)
                apply_public_error_payload(
                    cleanup_error,
                    replace(
                        public_error,
                        details={**cancellation_details, **(public_error.details or {})},
                    ),
                )
            exception = cleanup_error
    if isinstance(exception, TaskCancelledError | asyncio.CancelledError):
        if isinstance(exception, asyncio.CancelledError):
            await uncancel_then_cleanup(cancel_disconnect_action())
        await finalize_task_safely(
            registry=registry,
            task_id=task_context.task_id,
            status=TaskStatus.CANCELLED,
            trace_id=task_context.trace_id,
            operation=policy.cancelled_finalize_operation,
            result=cancellation_details or None,
            error_message=str(exception),
            status_message=str(exception),
        )
        if isinstance(exception, asyncio.CancelledError):
            raise exception
        raise_api_error_with_task(
            request,
            499,
            "cancelled",
            policy.cancelled_user_message,
            task_id=task_context.task_id,
            extra=cancellation_details or None,
        )
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
    if isinstance(exception, HANDLED_RUNTIME_EXCEPTIONS):
        public_error = project_public_exception(exception)
        if isinstance(exception, FilePublicationUncertainError | FileCleanupIncompleteError):
            public_error = replace(
                public_error,
                details={**(public_error.details or {}), "task_id": task_context.task_id},
            )
            apply_public_error_payload(exception, public_error)
        await finalize_task_safely(
            registry=registry,
            task_id=task_context.task_id,
            status=TaskStatus.FAILED,
            trace_id=task_context.trace_id,
            operation=policy.failed_finalize_operation,
            result=dict(public_error.details) if public_error.details else None,
            error_code=public_error.http_status or 500,
            error_type=str(public_error.code),
            error_message=public_error.message,
            status_message=public_error.message,
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
            public_error.http_status or 500,
            str(public_error.code),
            public_error.message,
            task_id=task_context.task_id,
            extra=dict(public_error.details) if public_error.details else None,
        )
    raise exception
