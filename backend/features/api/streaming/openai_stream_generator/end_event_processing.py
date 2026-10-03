"""SoAI - StreamEndEvent processing for OpenAI SSE [backend/features/api/streaming/openai_stream_generator/end_event_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from core.errors.exceptions import ModelOutputContractError
from core.events.types_models_streaming import StreamEndEvent
from core.openai.sse_frames import sse_done_chunk
from core.openai.streaming_usage import build_openai_usage_chunk_bytes
from core.openai.usage.serialization import extract_public_usage_payload
from core.streaming.protocols import StreamGeneratorStateProtocol
from features.api.streaming.openai_stream_generator.runtime_state import (
    OpenAIStreamRuntimeState,
)
from features.api.streaming.openai_stream_generator.stream_abort import (
    OpenAIStreamAbortRequested,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "finalize_openai_stream_frames",
    "iter_public_usage_chunk",
    "iter_stream_bytes_from_end_event",
)


def finalize_openai_stream_frames(state: OpenAIStreamRuntimeState) -> None:
    try:
        state.chunk_accumulator.finalize()
    except ModelOutputContractError as exception:
        state.is_stream_successful = False
        state.abort_stream = True
        raise OpenAIStreamAbortRequested(
            "Provider ended stream with an incomplete OpenAI SSE frame.",
            "invalid_stream_error",
        ) from exception


def iter_public_usage_chunk(
    state: OpenAIStreamRuntimeState,
    *,
    include_usage: bool,
    model: str | None,
    reported_usage: JSONValue,
) -> Iterator[bytes]:
    if not include_usage or state.is_done_sent:
        return
    public_usage = extract_public_usage_payload(reported_usage)
    if public_usage is None:
        public_usage = state.withheld_provider_usage
    if public_usage is None:
        return
    yield build_openai_usage_chunk_bytes(
        public_usage=public_usage,
        stream_id=state.stream_id,
        object_type=state.stream_object or "chat.completion.chunk",
        model=model,
    )


def iter_stream_bytes_from_end_event(
    end_event: StreamEndEvent,
    state: OpenAIStreamRuntimeState,
    *,
    include_usage: bool,
    model: str | None,
    emit_done_marker: bool,
    stream_result_state: StreamGeneratorStateProtocol | None,
) -> Iterator[bytes]:
    done_chunk = sse_done_chunk()
    finalize_openai_stream_frames(state)
    if state.stream_transcript is not None:
        state.stream_transcript.finalize()
        if stream_result_state is not None:
            if state.is_stream_successful:
                stream_result_state.payload = state.stream_transcript.build_result_payload()
            else:
                stream_result_state.partial_payload = state.stream_transcript.build_result_payload()
    if stream_result_state is not None and isinstance(end_event.usage, dict):
        stream_result_state.usage = dict(end_event.usage)
    yield from iter_public_usage_chunk(
        state,
        include_usage=include_usage,
        model=model,
        reported_usage=end_event.usage,
    )
    if emit_done_marker and not state.is_done_sent:
        yield done_chunk
        state.is_done_sent = True
