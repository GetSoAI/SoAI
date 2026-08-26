"""SoAI - Streaming iteration delivery helpers [backend/features/agent/runtime/streaming_iteration_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TYPE_CHECKING

from core.openai.openai_error_objects import (
    parse_openai_sse_error_frame_message_and_type,
)

if TYPE_CHECKING:
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.streaming.protocols import StreamGeneratorStateProtocol
    from features.agent.internal_protocols import AgentToolCallsDetectedCallback
    from features.openai.streaming_iteration_state import (
        AgentStreamingIterationState,
        FinalizedStreamingPayload,
    )

__all__ = (
    "collect_openai_stream_payload",
    "collect_streaming_iteration_payload",
    "emit_visible_text_deltas",
)


async def emit_visible_text_deltas(
    *,
    stream_transcript: OpenAIStreamTranscript,
    on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None] | None] | None,
) -> None:
    if on_visible_deltas is None:
        return
    deltas = stream_transcript.drain_visible_text_deltas()
    if not deltas:
        return
    result = on_visible_deltas(deltas)
    if result is not None:
        await result


async def collect_streaming_iteration_payload(
    stream_generator: AsyncIterator[bytes],
    iteration_state: AgentStreamingIterationState,
    stream_transcript: OpenAIStreamTranscript,
    stream_state: StreamGeneratorStateProtocol,
    on_bytes: Callable[[bytes], Awaitable[None] | None],
    on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None] | None] | None,
    on_tool_calls_detected: AgentToolCallsDetectedCallback | None,
    parse_error_chunk: Callable[[bytes], tuple[str, str] | None],
    should_skip_error_chunk: Callable[[tuple[str, str]], Awaitable[bool]],
) -> tuple[FinalizedStreamingPayload, tuple[str, str] | None]:
    captured_error: tuple[str, str] | None = None
    async for chunk in stream_generator:
        parsed_error = parse_error_chunk(chunk)
        if parsed_error is not None:
            captured_error = parsed_error
            if await should_skip_error_chunk(parsed_error):
                continue
        await iteration_state.emit_chunk(chunk, on_bytes=on_bytes)
        detected_tool_calls = stream_transcript.drain_new_tool_calls()
        if detected_tool_calls and on_tool_calls_detected is not None:
            offset_tool_calls = iteration_state.apply_offsets_to_detected_tool_calls(
                detected_tool_calls=detected_tool_calls,
                stream_transcript=stream_transcript,
            )
            detected_awaitable = on_tool_calls_detected(offset_tool_calls)
            if detected_awaitable is not None:
                await detected_awaitable
        await emit_visible_text_deltas(
            stream_transcript=stream_transcript,
            on_visible_deltas=on_visible_deltas,
        )
    await emit_visible_text_deltas(
        stream_transcript=stream_transcript,
        on_visible_deltas=on_visible_deltas,
    )
    finalized_payload = iteration_state.finalize_payload(
        stream_transcript=stream_transcript,
        stream_state=stream_state,
    )
    await emit_visible_text_deltas(
        stream_transcript=stream_transcript,
        on_visible_deltas=on_visible_deltas,
    )
    return finalized_payload, captured_error


async def collect_openai_stream_payload(
    stream_generator: AsyncIterator[bytes],
    iteration_state: AgentStreamingIterationState,
    stream_transcript: OpenAIStreamTranscript,
    stream_state: StreamGeneratorStateProtocol,
    on_bytes: Callable[[bytes], Awaitable[None] | None],
    on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None] | None] | None,
    on_tool_calls_detected: AgentToolCallsDetectedCallback | None,
    should_skip_error_chunk: Callable[[tuple[str, str]], Awaitable[bool]],
) -> tuple[FinalizedStreamingPayload, tuple[str, str] | None]:
    return await collect_streaming_iteration_payload(
        stream_generator,
        iteration_state,
        stream_transcript,
        stream_state,
        on_bytes,
        on_visible_deltas,
        on_tool_calls_detected,
        parse_openai_sse_error_frame_message_and_type,
        should_skip_error_chunk,
    )
