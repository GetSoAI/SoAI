"""SoAI - Streaming response construction for binary OpenAI endpoints [backend/features/api/streaming/openai_stream_binary_response.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.responses import Response, StreamingResponse

from core.events.types_files import FileContentQuery
from core.events.types_models_requests import TextToSpeechRequestReceived
from core.runtime.request_context import RequestContext
from features.api.openai.openai_error_responses import (
    build_openai_error_json_response_for_status,
)
from features.api.runtime.responses import (
    apply_task_id_header,
    build_task_operation_headers,
)
from features.api.streaming.openai_stream_binary_request_stream import (
    prepare_binary_stream_payload,
)
from features.api.streaming.openai_stream_sse_audio import stream_sse_audio_chunks
from features.api.streaming.sse_responses import create_sse_response
from features.api.streaming.stream_dependencies import build_stream_dependencies

if TYPE_CHECKING:
    import asyncio

    from core.events.types_base import Event
    from features.api.runtime.context import ApiContext

__all__ = ("build_binary_streaming_response",)


async def build_binary_streaming_response(
    *,
    api_context: ApiContext,
    reply_queue: asyncio.Queue[Event],
    context: RequestContext,
    trace_id: str | None,
    task_id: str,
    request_event_class: type[TextToSpeechRequestReceived | FileContentQuery],
    media_type: str,
    stream_format: str | None,
    resolved_model_id: str | None,
) -> Response:
    stream_dependencies = build_stream_dependencies(api_context.dependencies)
    stream_preparation = await prepare_binary_stream_payload(
        reply_queue=reply_queue,
        stream_dependencies=stream_dependencies,
        context=context,
        trace_id=trace_id,
    )
    if stream_preparation.stream is None:
        return build_openai_error_json_response_for_status(
            status_code=stream_preparation.status_code or 500,
            message=stream_preparation.error_message or "Internal server error.",
            soai_code=stream_preparation.error_type,
            param=None,
            trace_id=trace_id,
            headers=None,
        )

    normalized_stream_format = (stream_format or "").strip().lower()
    if normalized_stream_format == "sse" and request_event_class is TextToSpeechRequestReceived:
        additional_headers = build_task_operation_headers(task_id=task_id, operation_id=None)
        if resolved_model_id is not None:
            additional_headers["X-SoAI-Resolved-Model"] = resolved_model_id
        return create_sse_response(
            stream_sse_audio_chunks(stream_preparation.stream, trace_id or "no-trace"),
            additional_headers=additional_headers,
        )
    response = StreamingResponse(stream_preparation.stream, media_type=media_type)
    apply_task_id_header(response, task_id)
    if resolved_model_id is not None:
        response.headers["X-SoAI-Resolved-Model"] = resolved_model_id
    return response
