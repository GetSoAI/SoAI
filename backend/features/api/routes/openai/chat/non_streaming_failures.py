"""SoAI - Non-streaming OpenAI response failure handling [backend/features/api/routes/openai/chat/non_streaming_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_status,
)

if TYPE_CHECKING:
    from fastapi.responses import JSONResponse

    from core.tasks.protocols import TaskRegistryProtocol
    from core.tasks.task import Task
    from features.api.runtime.openai_context.internal_protocols import (
        OpenAIApiContextProtocol,
    )

__all__ = ("complete_task_stream_unavailable",)

LOGGER_NAME = "SoAI.features.api.non_streaming_failures"
OPERATION = "api_openai.handle_inference_request.finalize_task_stream_unavailable"


async def complete_task_stream_unavailable(
    api_context: OpenAIApiContextProtocol,
    *,
    registry: TaskRegistryProtocol,
    task: Task,
    context: RequestContext,
) -> JSONResponse:
    try:
        await finalize(
            registry,
            task.task_id,
            TaskStatus.FAILED,
            error_code=503,
            error_message="Task stream unavailable.",
        )
    except RECOVERABLE_EXCEPTIONS as cleanup_exception:
        log_handled_exception(
            get_logger(LOGGER_NAME),
            cleanup_exception,
            message="Task failure cleanup suppressed (non-critical).",
            trace_id=context.trace_id,
            operation=OPERATION,
            details={"task_id": task.task_id},
            level="debug",
        )
    api_context.dependencies.metrics_manager.increment_counter("api", "openai", "requests_failed")
    return build_openai_error_json_response_for_status(
        status_code=503,
        message="Task stream unavailable.",
        soai_code="task_stream_unavailable",
        param=None,
        trace_id=context.trace_id,
        headers=None,
    )
