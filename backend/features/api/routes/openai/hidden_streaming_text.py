"""SoAI - Hidden streaming inference to final text helpers [backend/features/api/routes/openai/hidden_streaming_text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ModelOutputContractError, ValidationError
from core.events.types_base import Event
from core.events.types_models_streaming import (
    InferenceResultEvent,
    StreamChunkEvent,
    StreamEndEvent,
)
from core.events.types_tasks import TaskCompleteEvent
from core.openai.reasoning_text import normalize_reasoning_text
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.runtime.protocols import RequestProtocol
from features.agent.runtime.openai_payload import extract_assistant_content_raw
from features.api.routes.openai.non_streaming_errors import (
    raise_malformed_stream_chunk_error,
    raise_task_completed_without_result,
    raise_task_succeeded_without_payload,
)
from features.api.routes.openai.non_streaming_event_loop import (
    run_non_streaming_event_loop,
)
from features.api.streaming.non_streaming_sse_reconstructor import (
    NonStreamingSSEMalformedFrameError,
    NonStreamingSSEReconstructor,
)
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict

__all__ = (
    "HiddenStreamingEmptyResponseError",
    "await_hidden_streaming_text",
    "extract_hidden_response_text",
)


class HiddenStreamingEmptyResponseError(ValidationError): ...


def _strip_system_reminder_blocks(value: str) -> str:
    text = value
    while True:
        start_index = text.lower().find("<system-reminder>")
        if start_index < 0:
            return text
        end_index = text.lower().find("</system-reminder>", start_index)
        if end_index < 0:
            return text[:start_index]
        text = (text[:start_index] + text[end_index + len("</system-reminder>") :]).strip()


def _extract_hidden_visible_text(result_payload: JSONDict) -> str:
    hidden_text = extract_assistant_content_raw(result_payload).strip()
    if not hidden_text:
        return ""
    return _strip_system_reminder_blocks(hidden_text).strip()


async def await_hidden_streaming_text(
    *,
    request: RequestProtocol,
    context: RequestContext,
    stream_dependencies: StreamDependencies,
    request_json: JSONDict,
    reply_queue: asyncio.Queue[Event],
    task_id: str,
    timeout: float,
    on_text_delta: Callable[[str], Awaitable[None]] | None,
    allow_reasoning_fallback: bool = True,
    empty_response_message: str = "Hidden inference returned an empty response.",
) -> str:
    reconstructor = NonStreamingSSEReconstructor(
        allow_image_events=False,
        converter_format="chat",
    )
    delivered_content_parts: list[str] = []

    async def emit_pending_text_delta(result_payload: JSONDict) -> None:
        if on_text_delta is None:
            return
        content = extract_assistant_content_raw(result_payload)
        if not content:
            return
        delivered = "".join(delivered_content_parts)
        if not content.startswith(delivered):
            return
        remaining = content[len(delivered) :]
        if not remaining:
            return
        await on_text_delta(remaining)

    def finalize_buffered_stream() -> JSONDict | None:
        try:
            return reconstructor.finalize()
        except (ModelOutputContractError, NonStreamingSSEMalformedFrameError):
            raise_malformed_stream_chunk_error(request)

    async def on_inference_result(result_event: InferenceResultEvent) -> JSONDict:
        finalize_buffered_stream()
        await emit_pending_text_delta(result_event.payload)
        return result_event.payload

    async def on_stream_chunk(result_event: StreamChunkEvent) -> None:
        try:
            reconstructor.consume_chunk(
                context=context,
                request_json=request_json,
                chunk=result_event.chunk,
                buffering_log_label="hidden inference",
            )
        except (ModelOutputContractError, NonStreamingSSEMalformedFrameError):
            raise_malformed_stream_chunk_error(request)
        stream_transcript = reconstructor.transcript
        if on_text_delta is None or stream_transcript is None:
            return
        for delta in stream_transcript.drain_visible_text_deltas():
            delivered_content_parts.append(delta)
            await on_text_delta(delta)

    async def on_stream_end(_result_event: StreamEndEvent) -> JSONDict:
        result_payload = finalize_buffered_stream()
        if result_payload is None:
            raise_task_succeeded_without_payload(request)
        await emit_pending_text_delta(result_payload)
        return result_payload

    async def on_task_complete(result_event: TaskCompleteEvent) -> JSONDict:
        result_payload = finalize_buffered_stream()
        if result_payload is not None:
            await emit_pending_text_delta(result_payload)
            return result_payload
        if result_event.success:
            raise_task_succeeded_without_payload(request)
        raise_task_completed_without_result(request, result_event.message)

    result_payload = await run_non_streaming_event_loop(
        request=request,
        stream_dependencies=stream_dependencies,
        reply_queue=reply_queue,
        task_id=task_id,
        timeout=timeout,
        on_inference_result=on_inference_result,
        on_stream_chunk=on_stream_chunk,
        on_stream_end=on_stream_end,
        on_task_complete=on_task_complete,
    )
    return extract_hidden_response_text(
        result_payload,
        stream_transcript=reconstructor.transcript,
        allow_reasoning_fallback=allow_reasoning_fallback,
        empty_response_message=empty_response_message,
    )


def extract_hidden_response_text(
    result_payload: JSONDict,
    *,
    stream_transcript: OpenAIStreamTranscript | None = None,
    allow_reasoning_fallback: bool = True,
    empty_response_message: str = "Hidden inference returned an empty response.",
) -> str:
    if stream_transcript is not None:
        visible_text = stream_transcript.get_visible_text().strip()
        if visible_text:
            return _strip_system_reminder_blocks(visible_text).strip()
        if allow_reasoning_fallback:
            thinking_text = stream_transcript.get_thinking_text().strip()
            if thinking_text:
                return _strip_system_reminder_blocks(thinking_text).strip()

    hidden_text = _extract_hidden_visible_text(result_payload)
    if hidden_text:
        return hidden_text

    if allow_reasoning_fallback:
        choices = result_payload.get("choices") if isinstance(result_payload, dict) else None
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message_value = choice.get("message")
                message = message_value if isinstance(message_value, dict) else None
                if message is None:
                    continue
                reasoning_payload = (
                    message.get("reasoning_content")
                    if "reasoning_content" in message
                    else (
                        message.get("reasoning")
                        if "reasoning" in message
                        else message.get("thinking")
                    )
                )
                reasoning_text = normalize_reasoning_text(reasoning_payload).strip()
                if reasoning_text:
                    return _strip_system_reminder_blocks(reasoning_text).strip()

    raise HiddenStreamingEmptyResponseError(empty_response_message)
