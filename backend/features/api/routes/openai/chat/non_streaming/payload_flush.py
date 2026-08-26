"""SoAI - Non-streaming SSE payload finalization [backend/features/api/routes/openai/chat/non_streaming/payload_flush.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi.responses import JSONResponse

from core.errors.exceptions import ModelOutputContractError
from core.runtime.request_context import RequestContext
from core.tasks.task import Task
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_status,
)
from features.api.routes.openai.chat.inference_payload import (
    handle_inference_payload_response,
)
from features.api.routes.openai.non_streaming_errors import (
    MALFORMED_STREAM_CHUNK_MESSAGE,
)
from features.api.runtime.openai_context.internal_protocols import (
    OpenAIApiContextProtocol,
)
from features.api.streaming.non_streaming_sse_reconstructor import (
    NonStreamingSSEMalformedFrameError,
    NonStreamingSSEReconstructor,
)

__all__ = (
    "flush_and_handle_stream_end",
    "flush_and_handle_task_complete",
)


def _build_malformed_sse_error_response(
    api_context: OpenAIApiContextProtocol,
    context: RequestContext,
) -> JSONResponse:
    api_context.dependencies.metrics_manager.increment_counter("api", "openai", "requests_failed")
    return build_openai_error_json_response_for_status(
        status_code=502,
        message=MALFORMED_STREAM_CHUNK_MESSAGE,
        soai_code="invalid_stream_error",
        param=None,
        trace_id=context.trace_id,
        headers=None,
    )


async def flush_and_handle_stream_end(
    api_context: OpenAIApiContextProtocol,
    *,
    context: RequestContext,
    reconstructor: NonStreamingSSEReconstructor,
    task: Task,
) -> JSONResponse:
    try:
        result_payload = reconstructor.finalize()
    except (ModelOutputContractError, NonStreamingSSEMalformedFrameError):
        return _build_malformed_sse_error_response(api_context, context)
    if result_payload is not None:
        return await handle_inference_payload_response(
            api_context,
            context,
            result_payload,
            task,
        )
    api_context.dependencies.metrics_manager.increment_counter("api", "openai", "requests_failed")
    return build_openai_error_json_response_for_status(
        status_code=502,
        message="Provider reported stream end without a reconstructable non-streaming payload.",
        soai_code="invalid_stream_error",
        param=None,
        trace_id=context.trace_id,
        headers=None,
    )


async def flush_and_handle_task_complete(
    api_context: OpenAIApiContextProtocol,
    *,
    context: RequestContext,
    reconstructor: NonStreamingSSEReconstructor,
    task: Task,
    success: bool,
    message: str,
) -> JSONResponse:
    try:
        result_payload = reconstructor.finalize()
    except (ModelOutputContractError, NonStreamingSSEMalformedFrameError):
        return _build_malformed_sse_error_response(api_context, context)
    if result_payload is not None:
        return await handle_inference_payload_response(
            api_context,
            context,
            result_payload,
            task,
        )
    api_context.dependencies.metrics_manager.increment_counter("api", "openai", "requests_failed")
    if success:
        return build_openai_error_json_response_for_status(
            status_code=502,
            message="Task completed successfully but provider did not return a reconstructable payload.",
            soai_code="invalid_stream_error",
            param=None,
            trace_id=context.trace_id,
            headers=None,
        )
    return build_openai_error_json_response_for_status(
        status_code=500,
        message=message or "Task completed without result.",
        soai_code=None,
        param=None,
        trace_id=context.trace_id,
        headers=None,
    )
