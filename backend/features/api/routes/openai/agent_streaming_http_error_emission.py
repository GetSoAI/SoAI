"""SoAI - Agent streaming HTTP error emission helpers [backend/features/api/routes/openai/agent_streaming_http_error_emission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import HTTPException

from core.errors.exceptions import ApiError
from core.errors.public_projection import project_public_error
from core.openai.openai_error_objects import (
    parse_openai_http_exception_detail_message_and_type,
)
from core.openai.sse_events import format_openai_stream_error_chunk
from features.agent.internal_protocols import AgentStreamingInferenceOutcome
from features.agent.runtime.streaming_inference_outcomes import (
    build_agent_streaming_inference_outcome,
)

__all__ = (
    "emit_api_error_and_build_outcome",
    "emit_http_exception_and_build_outcome",
)


async def emit_http_exception_and_build_outcome(
    exception: HTTPException,
    *,
    format_error_chunk: Callable[[str, str, str], str] | None,
    trace_id: str,
    on_bytes: Callable[[bytes], Awaitable[None] | None],
) -> AgentStreamingInferenceOutcome:
    if exception.status_code >= 500:
        message_text = "Internal server error."
        http_error_type = "server_error"
    else:
        message_text, http_error_type = parse_openai_http_exception_detail_message_and_type(
            exception.detail,
        )
    return await _emit_error_and_build_outcome(
        message_text,
        http_error_type,
        format_error_chunk=format_error_chunk,
        trace_id=trace_id,
        on_bytes=on_bytes,
    )


async def emit_api_error_and_build_outcome(
    exception: ApiError,
    *,
    format_error_chunk: Callable[[str, str, str], str] | None,
    trace_id: str,
    on_bytes: Callable[[bytes], Awaitable[None] | None],
) -> AgentStreamingInferenceOutcome:
    public_payload = project_public_error(exception, trace_id=trace_id)
    message_text = public_payload.message
    error_type = str(public_payload.code)
    return await _emit_error_and_build_outcome(
        message_text,
        error_type,
        format_error_chunk=format_error_chunk,
        trace_id=trace_id,
        on_bytes=on_bytes,
    )


async def _emit_error_and_build_outcome(
    message_text: str,
    error_type: str,
    *,
    format_error_chunk: Callable[[str, str, str], str] | None,
    trace_id: str,
    on_bytes: Callable[[bytes], Awaitable[None] | None],
) -> AgentStreamingInferenceOutcome:
    error_bytes = format_openai_stream_error_chunk(
        format_error_chunk,
        message_text,
        error_type,
        trace_id,
    )
    awaitable = on_bytes(error_bytes)
    if awaitable is not None:
        await awaitable
    return build_agent_streaming_inference_outcome(
        payload=None,
        stream_successful=False,
        done_sent=False,
        error_message=message_text,
        error_type=error_type,
    )
