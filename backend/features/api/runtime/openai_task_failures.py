"""SoAI - OpenAI task creation failure handling [backend/features/api/runtime/openai_task_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi.responses import JSONResponse

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.runtime.protocols import RequestContextProtocol
from core.tasks.errors import TaskIDCollisionError
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_status,
)
from features.api.runtime.openai_error_conversion import (
    build_openai_soai_error_response,
)

__all__ = ("handle_task_creation_failure",)

OPERATION_FEATURES_API_STREAMING_OPENAI_STREAM_TASK_FAILURES_HANDLE_TASK_CREATION_FAILURE = (
    "features.api.runtime.openai_task_failures.handle_task_creation_failure"
)


LOGGER_NAME = "SoAI.features.api.openai_task_failures"


def handle_task_creation_failure(
    exception: Exception,
    context: RequestContextProtocol,
    operation: str,
    metrics_manager: MetricsManagerProtocol,
) -> JSONResponse:
    logger = get_logger(LOGGER_NAME)
    try:
        trace_id = context.trace_id
    except AttributeError:
        trace_id = None
    if isinstance(exception, ValidationError):
        log_handled_exception(
            logger,
            exception,
            message="Rejected OpenAI execution request during admission.",
            trace_id=trace_id,
            operation=OPERATION_FEATURES_API_STREAMING_OPENAI_STREAM_TASK_FAILURES_HANDLE_TASK_CREATION_FAILURE,
            level="info",
            details={"operation": operation},
        )
    else:
        log_exception(
            logger,
            exception,
            message="Failed to admit OpenAI execution request.",
            trace_id=trace_id,
            operation=OPERATION_FEATURES_API_STREAMING_OPENAI_STREAM_TASK_FAILURES_HANDLE_TASK_CREATION_FAILURE,
            level="error",
            details={"operation": operation},
        )
    if metrics_manager is not None:
        metrics_manager.increment_counter("api", "openai", "requests_failed")
    if isinstance(exception, TaskIDCollisionError):
        message = f"Task with ID '{exception.task_id}' already exists (status: {exception.existing_status})."
        return build_openai_error_json_response_for_status(
            status_code=409,
            message=message,
            soai_code="task_id_collision",
            param=None,
            trace_id=trace_id,
            headers=None,
        )
    if isinstance(exception, SoAIError):
        return build_openai_soai_error_response(exception, trace_id=trace_id)
    return build_openai_error_json_response_for_status(
        status_code=500,
        message="Failed to admit the requested OpenAI execution request.",
        soai_code=None,
        param=None,
        trace_id=trace_id,
        headers=None,
    )
