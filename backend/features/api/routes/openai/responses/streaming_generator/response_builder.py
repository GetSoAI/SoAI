"""SoAI - OpenAI Responses passthrough streaming response builder [backend/features/api/routes/openai/responses/streaming_generator/response_builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Request
from starlette.responses import Response

from core.types.json import JSONDict
from features.api.routes.openai.responses.passthrough_task_setup import (
    ResponsesTaskSetupResult,
)
from features.api.routes.openai.responses.streaming_generator.generator import (
    responses_passthrough_stream_generator,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.responses import build_task_operation_headers
from features.api.streaming.sse_responses import create_sse_response

__all__ = ("create_passthrough_responses_streaming_response",)


def create_passthrough_responses_streaming_response(
    *,
    request: Request,
    api_context: ApiContext,
    task_setup: ResponsesTaskSetupResult,
    request_json: JSONDict,
) -> Response:
    context = request.state.context
    return create_sse_response(
        responses_passthrough_stream_generator(
            task_setup=task_setup,
            api_context=api_context,
            request=request,
            request_json=request_json,
        ),
        additional_headers=build_task_operation_headers(
            task_id=task_setup.task.task_id,
            operation_id=context.trace_id,
        ),
    )
