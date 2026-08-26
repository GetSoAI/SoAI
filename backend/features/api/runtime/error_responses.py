"""SoAI - API error responses and publish failure handling [backend/features/api/runtime/error_responses.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi.responses import JSONResponse

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.protocols import TaskRegistryProtocol
from core.types.json import JSONDict
from features.api.runtime.boundary_error_responses import (
    build_soai_error_json_response_for_status,
)

__all__ = (
    "create_error_response",
    "handle_publish_error",
)


def create_error_response(
    status_code: int,
    message: str,
    error_type: str,
    trace_id: str | None = None,
    details: JSONDict | None = None,
) -> JSONResponse:
    return build_soai_error_json_response_for_status(
        status_code=status_code,
        message=message,
        soai_code=error_type,
        details=details,
        trace_id=trace_id,
    )


async def handle_publish_error(
    registry: TaskRegistryProtocol,
    task_id: str,
    exception: Exception,
    trace_id: str | None,
    operation: str,
    is_soai_error: bool,
    logger_instance: LoggerProtocol,
) -> JSONResponse:
    error_code = 503 if is_soai_error else 500
    error_message = (
        "System event bus is not available."
        if is_soai_error
        else "Internal error publishing inference event."
    )
    try:
        await finalize(
            registry,
            task_id,
            TaskStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
        )
    except RECOVERABLE_EXCEPTIONS as fail_exception:
        log_handled_exception(
            logger_instance,
            fail_exception,
            message="Failed to mark task as failed (non-critical).",
            trace_id=trace_id,
            operation=operation,
            level="debug",
        )
    log_level = "critical" if is_soai_error else "error"
    log_message = (
        "Failed to publish inference event."
        if is_soai_error
        else "Unhandled error while publishing inference event."
    )
    log_exception(
        logger_instance,
        exception,
        message=log_message,
        trace_id=trace_id,
        operation=operation,
        level=log_level,
    )
    response_message = (
        "System event bus is not available." if is_soai_error else "Internal server error."
    )
    return create_error_response(error_code, response_message, "server_error", trace_id)
