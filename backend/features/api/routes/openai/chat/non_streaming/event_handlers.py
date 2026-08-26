"""SoAI - Non-streaming inference event handlers [backend/features/api/routes/openai/chat/non_streaming/event_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi.responses import JSONResponse

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.tasks.task_cancellation import cancel
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_status,
)
from features.api.runtime.openai_context.internal_protocols import (
    OpenAIApiContextProtocol,
)

__all__ = (
    "cancel_and_return_error",
    "handle_client_disconnect",
    "handle_shutdown",
    "handle_timeout",
)

LOGGER_NAME = "SoAI.features.api.event_handlers"
OPERATION = "api_openai.handle_inference_request"


async def handle_shutdown(
    api_context: OpenAIApiContextProtocol,
    *,
    registry: TaskRegistryProtocol,
    task: Task,
    context: RequestContext,
) -> JSONResponse:
    try:
        await cancel(
            registry,
            task.task_id,
            reason="SoAI API Server is shutting down.",
            context=context,
        )
    except RECOVERABLE_EXCEPTIONS as cancel_exc:
        coerced_cancel = coerce_to_soai_error(
            cancel_exc,
            operation="api_openai.handle_inference_request",
        )
        log_handled_exception(
            get_logger(LOGGER_NAME),
            coerced_cancel,
            message="Failed to cancel task on shutdown (non-critical).",
            trace_id=context.trace_id,
            operation=OPERATION,
            level="debug",
        )
    api_context.dependencies.metrics_manager.increment_counter("api", "openai", "requests_failed")
    return build_openai_error_json_response_for_status(
        status_code=503,
        message="SoAI API Server is shutting down.",
        soai_code="service_unavailable",
        param=None,
        trace_id=context.trace_id,
        headers=None,
    )


async def handle_timeout(
    api_context: OpenAIApiContextProtocol,
    *,
    registry: TaskRegistryProtocol,
    task: Task,
    context: RequestContext,
    timeout: float,
) -> JSONResponse:
    try:
        await cancel(
            registry,
            task.task_id,
            reason=f"Timed out after {timeout} seconds.",
            context=context,
        )
    except RECOVERABLE_EXCEPTIONS as timeout_exc:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            timeout_exc,
            message="Failed to cancel task on timeout (non-critical).",
            trace_id=context.trace_id,
            operation=OPERATION,
            level="debug",
        )
    api_context.dependencies.metrics_manager.increment_counter("api", "openai", "requests_failed")
    return build_openai_error_json_response_for_status(
        status_code=504,
        message=f"Request timed out after {timeout} seconds.",
        soai_code="timeout_error",
        param=None,
        trace_id=context.trace_id,
        headers=None,
    )


async def handle_client_disconnect(
    api_context: OpenAIApiContextProtocol,
    *,
    registry: TaskRegistryProtocol,
    task: Task,
    context: RequestContext,
) -> JSONResponse:
    if api_context.dependencies.config.get_bool("MODELS.ROUTING.CANCEL_ON_CLIENT_DISCONNECT"):
        try:
            await cancel(registry, task.task_id, reason="Client disconnected.", context=context)
        except RECOVERABLE_EXCEPTIONS as cancel_exc:
            log_handled_exception(
                get_logger(LOGGER_NAME),
                cancel_exc,
                message="Failed to cancel task on client disconnect (non-critical).",
                trace_id=context.trace_id,
                operation=OPERATION,
                level="debug",
            )
    api_context.dependencies.metrics_manager.increment_counter("api", "openai", "requests_failed")
    return build_openai_error_json_response_for_status(
        status_code=499,
        message="Client disconnected.",
        soai_code=None,
        param=None,
        trace_id=context.trace_id,
        headers=None,
    )


async def cancel_and_return_error(
    api_context: OpenAIApiContextProtocol,
    *,
    registry: TaskRegistryProtocol,
    task: Task,
    context: RequestContext,
    status_code: int,
    message: str,
    error_type: str,
) -> JSONResponse:
    try:
        await cancel(registry, task.task_id, reason=message, context=context)
    except RECOVERABLE_EXCEPTIONS as cancel_exc:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            cancel_exc,
            message="Failed to cancel task after invalid non-streaming SSE payload (non-critical).",
            trace_id=context.trace_id,
            operation=OPERATION,
            level="debug",
        )
    api_context.dependencies.metrics_manager.increment_counter("api", "openai", "requests_failed")
    return build_openai_error_json_response_for_status(
        status_code=int(status_code),
        message=message,
        soai_code=error_type,
        param=None,
        trace_id=context.trace_id,
        headers=None,
    )
