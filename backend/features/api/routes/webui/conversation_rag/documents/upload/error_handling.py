"""SoAI - RAG document upload error handling [backend/features/api/routes/webui/conversation_rag/documents/upload/error_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, NoReturn

from core.concurrency.cancellation import TaskCancelledError
from core.errors.exception_logging import log_exception
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    PayloadTooLargeError,
    RateLimitError,
    ValidationError,
)
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.tasks.enums import TaskStatus
from features.api.runtime.task_api_errors import (
    finalize_task_and_raise_api_error,
    raise_api_error_with_task,
)
from features.api.runtime.task_execution import (
    cancel_task_after_disconnect_safely,
    finalize_task_safely,
)
from features.api.runtime.upload_error_resolution import resolve_upload_api_error

if TYPE_CHECKING:
    from fastapi import Request

    from core.runtime.request_context import RequestContext
    from core.tasks.protocols import TaskRegistryProtocol

__all__ = ("handle_rag_document_upload_exception",)

OPERATION_WEBUI_UPLOAD_RAG_DOCUMENT = "webui.conversation_rag.upload_document"
OPERATION_WEBUI_UPLOAD_RAG_DOCUMENT_CANCEL_AFTER_DISCONNECT = (
    "webui.conversation_rag.upload_document.cancel_after_disconnect"
)


async def handle_rag_document_upload_exception(
    request: Request,
    *,
    exception: BaseException,
    registry: TaskRegistryProtocol,
    task_id: str,
    context: RequestContext,
    logger: LoggerProtocol,
    resolved_id: str,
    filename: str,
) -> NoReturn:
    try:
        trace_id = context.trace_id
    except AttributeError:
        trace_id = None
    if isinstance(exception, TaskCancelledError):
        await finalize_task_and_raise_api_error(
            request,
            registry=registry,
            task_id=task_id,
            task_status=TaskStatus.CANCELLED,
            trace_id=trace_id,
            operation="webui.conversation_rag.upload_document.finalize_cancelled",
            http_status=499,
            error_type="cancelled",
            error_message="RAG document upload was cancelled.",
            task_error_message=str(exception),
            status_message=str(exception),
        )
    if isinstance(exception, asyncio.CancelledError):
        await cancel_task_after_disconnect_safely(
            registry=registry,
            task_id=task_id,
            operation=OPERATION_WEBUI_UPLOAD_RAG_DOCUMENT_CANCEL_AFTER_DISCONNECT,
            trace_id=trace_id,
        )
        raise exception
    if isinstance(
        exception,
        InsufficientDiskSpaceError | PayloadTooLargeError | RateLimitError | ValidationError,
    ):
        error_http_status, error_code, error_message, status_message, error_headers = (
            resolve_upload_api_error(
                exception,
                default_server_message="Failed to upload RAG document.",
            )
        )
        await finalize_task_and_raise_api_error(
            request,
            registry=registry,
            task_id=task_id,
            task_status=TaskStatus.FAILED,
            trace_id=trace_id,
            operation="webui.conversation_rag.upload_document.finalize_failed",
            http_status=error_http_status,
            error_type=error_code,
            error_message=error_message,
            error_code=error_http_status,
            status_message=status_message,
            headers=error_headers,
        )
    if isinstance(exception, RECOVERABLE_EXCEPTIONS):
        await finalize_task_safely(
            registry=registry,
            task_id=task_id,
            status=TaskStatus.FAILED,
            trace_id=trace_id,
            operation="webui.conversation_rag.upload_document.finalize_failed",
            error_code=500,
            error_message=str(exception),
        )
        log_exception(
            logger,
            exception,
            message="Failed to stage RAG document upload.",
            operation=OPERATION_WEBUI_UPLOAD_RAG_DOCUMENT,
            details={"conv_id": resolved_id, "filename": filename, "task_id": task_id},
        )
        raise_api_error_with_task(
            request,
            500,
            "server_error",
            "Failed to upload RAG document.",
            task_id=task_id,
        )
    raise exception
