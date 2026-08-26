"""SoAI - API command cleanup and task failure handling [backend/features/api/runtime/response_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Request

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task_cancellation import cancel
from features.api.runtime.errors import raise_gateway_timeout

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext

__all__ = (
    "handle_dispatch_cancellation",
    "handle_dispatch_soai_error",
    "handle_dispatch_timeout",
    "handle_dispatch_unexpected_error",
)

LOGGER_NAME = "SoAI.features.api.response_cleanup"
OPERATION_API_RUNTIME_CANCEL_AFTER_DISCONNECT = "api_runtime.cancel_after_disconnect"
OPERATION_API_RUNTIME_CANCEL_AFTER_TIMEOUT = "api_runtime.cancel_after_timeout"
OPERATION_API_RUNTIME_FINALIZE_AFTER_EXCEPTION = "api_runtime.finalize_after_exception"
OPERATION_API_RUNTIME_FINALIZE_AFTER_SOAI_ERROR = "api_runtime.finalize_after_soai_error"


async def handle_dispatch_cancellation(
    registry: TaskRegistryProtocol,
    task_id: str,
    context: RequestContext | None,
) -> None:
    try:
        await cancel(
            registry,
            task_id,
            reason="Client disconnected.",
            context=context,
        )
    except RECOVERABLE_EXCEPTIONS as cleanup_exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            cleanup_exception,
            message="Task cancellation cleanup suppressed (non-critical).",
            operation=OPERATION_API_RUNTIME_CANCEL_AFTER_DISCONNECT,
            details={"task_id": task_id},
            level="debug",
        )


async def handle_dispatch_timeout(
    request: Request,
    registry: TaskRegistryProtocol,
    task_id: str,
    command_name: str,
) -> None:
    context = request.state.context
    try:
        await cancel(
            registry,
            task_id,
            reason=f"Command '{command_name}' timed out.",
            context=context,
        )
    except RECOVERABLE_EXCEPTIONS as cleanup_exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            cleanup_exception,
            message="Task timeout cleanup suppressed (non-critical).",
            operation=OPERATION_API_RUNTIME_CANCEL_AFTER_TIMEOUT,
            details={"task_id": task_id},
            level="debug",
        )
    raise_gateway_timeout(request, f"Command '{command_name}' timed out.")


async def handle_dispatch_soai_error(
    registry: TaskRegistryProtocol,
    task_id: str,
    exception: SoAIError,
) -> None:
    try:
        await finalize(
            registry,
            task_id,
            TaskStatus.FAILED,
            error_code=exception.http_status,
            error_message=exception.message,
        )
    except RECOVERABLE_EXCEPTIONS as cleanup_exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            cleanup_exception,
            message="Task failure cleanup suppressed (non-critical).",
            operation=OPERATION_API_RUNTIME_FINALIZE_AFTER_SOAI_ERROR,
            details={"task_id": task_id},
            level="debug",
        )


async def handle_dispatch_unexpected_error(
    registry: TaskRegistryProtocol,
    task_id: str,
    exception: BaseException,
) -> None:
    try:
        await finalize(
            registry,
            task_id,
            TaskStatus.FAILED,
            error_code=500,
            error_message=f"Unexpected error: {type(exception).__name__}",
        )
    except RECOVERABLE_EXCEPTIONS as cleanup_exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            cleanup_exception,
            message="Task failure cleanup suppressed (non-critical).",
            operation=OPERATION_API_RUNTIME_FINALIZE_AFTER_EXCEPTION,
            details={"task_id": task_id},
            level="debug",
        )
