"""SoAI - Shared OpenAI streaming iteration state [backend/features/openai/streaming_iteration_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.openai.streaming_tool_calls import inject_collected_tool_calls_into_payload
from core.openai.tool_calls import normalize_tool_calls_preserving_chronology
from core.streaming.protocols import StreamGeneratorStateProtocol
from core.validation.integers import is_strict_int
from features.agent.internal_protocols import AgentStreamingInferenceOutcome
from features.openai.streaming_chunk_emitter import (
    AgentStreamingChunkEmitter,
)
from features.openai.streaming_tool_call_offsets import (
    apply_collected_tool_call_offsets,
)

if TYPE_CHECKING:
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.types.json import JSONDict

__all__ = (
    "AgentStreamingIterationState",
    "FinalizedStreamingPayload",
    "build_cancelled_stream_outcome",
)

LOGGER_NAME = "SoAI.features.openai.streaming_iteration_state"


@dataclass(frozen=True, slots=True)
class FinalizedStreamingPayload:
    payload: JSONDict | None
    tool_calls: list[JSONDict]
    visible_text_chars: int
    thinking_text_chars: int
    content_index_base: int
    thinking_index_base: int
    tool_sequence_offset_base: int
    next_tool_sequence_offset: int
    next_content_index_offset: int
    next_thinking_index_offset: int


@dataclass(slots=True)
class AgentStreamingIterationState:
    chunk_emitter: AgentStreamingChunkEmitter = field(default_factory=AgentStreamingChunkEmitter)

    @property
    def root_stream_id(self) -> str | None:
        return self.chunk_emitter.root_stream_id

    @property
    def root_stream_created(self) -> int | None:
        return self.chunk_emitter.root_stream_created

    async def emit_chunk(
        self,
        chunk: bytes,
        *,
        on_bytes: Callable[[bytes], Awaitable[None] | None],
    ) -> None:
        await self.chunk_emitter.emit_chunk(chunk, on_bytes=on_bytes)

    def apply_offsets_to_detected_tool_calls(
        self,
        *,
        detected_tool_calls: list[JSONDict],
        stream_transcript: OpenAIStreamTranscript,
    ) -> tuple[JSONDict, ...]:
        if not detected_tool_calls:
            return ()
        offset_tool_calls = [dict(tool_call) for tool_call in detected_tool_calls]
        content_index_base = self.chunk_emitter.content_index_offset
        thinking_index_base = self.chunk_emitter.thinking_index_offset
        apply_collected_tool_call_offsets(
            collected_tool_calls=offset_tool_calls,
            tool_sequence_offset=self.chunk_emitter.tool_sequence_offset,
            content_index_base=content_index_base,
            thinking_index_base=thinking_index_base,
            content_index_upper_bound=(
                content_index_base + stream_transcript.get_visible_content_char_count()
            ),
            thinking_index_upper_bound=(
                thinking_index_base + stream_transcript.get_thinking_char_count()
            ),
        )
        return tuple(offset_tool_calls)

    def finalize_payload(
        self,
        *,
        stream_transcript: OpenAIStreamTranscript | None,
        stream_state: StreamGeneratorStateProtocol,
    ) -> FinalizedStreamingPayload:
        if stream_transcript is not None:
            stream_transcript.finalize()
            tool_call_contract_violation = (
                stream_transcript.get_tool_call_contract_violation_summary()
            )
            if tool_call_contract_violation is not None:
                logger = get_logger(LOGGER_NAME)
                logger.warning(
                    "Observed upstream streamed tool-call contract violation during payload finalization: %s",
                    tool_call_contract_violation,
                )
        raw_collected_tool_calls = (
            stream_transcript.get_tool_calls() if stream_transcript is not None else []
        )
        normalized_collected_tool_calls: list[JSONDict] = []
        content_index_base = self.chunk_emitter.content_index_offset
        thinking_index_base = self.chunk_emitter.thinking_index_offset
        content_index_upper_bound = content_index_base
        thinking_index_upper_bound = thinking_index_base
        visible_text_chars = 0
        thinking_text_chars = 0
        next_tool_sequence_offset = self.chunk_emitter.tool_sequence_offset
        next_content_index_offset = content_index_base
        next_thinking_index_offset = thinking_index_base
        if stream_transcript is not None:
            visible_text_chars = stream_transcript.get_visible_content_char_count()
            thinking_text_chars = stream_transcript.get_thinking_char_count()
            next_content_index_offset = content_index_base + visible_text_chars
            next_thinking_index_offset = thinking_index_base + thinking_text_chars
            content_index_upper_bound = next_content_index_offset
            thinking_index_upper_bound = next_thinking_index_offset
        if raw_collected_tool_calls:
            next_tool_sequence_offset = apply_collected_tool_call_offsets(
                collected_tool_calls=raw_collected_tool_calls,
                tool_sequence_offset=self.chunk_emitter.tool_sequence_offset,
                content_index_base=content_index_base,
                thinking_index_base=thinking_index_base,
                content_index_upper_bound=content_index_upper_bound,
                thinking_index_upper_bound=thinking_index_upper_bound,
            )
            normalized_collected_tool_calls = normalize_tool_calls_preserving_chronology(
                raw_collected_tool_calls,
            )
        payload_value = (
            stream_state.payload
            if stream_state.payload is not None
            else stream_state.partial_payload
        )
        if payload_value is not None and raw_collected_tool_calls:
            inject_collected_tool_calls_into_payload(payload_value, raw_collected_tool_calls)
        if payload_value is not None and self.chunk_emitter.root_stream_id is not None:
            payload_value["id"] = self.chunk_emitter.root_stream_id
            created_value = payload_value.get("created")
            if self.chunk_emitter.root_stream_created is not None and is_strict_int(created_value):
                payload_value["created"] = self.chunk_emitter.root_stream_created
        return FinalizedStreamingPayload(
            payload=payload_value,
            tool_calls=[dict(tool_call) for tool_call in normalized_collected_tool_calls],
            visible_text_chars=visible_text_chars,
            thinking_text_chars=thinking_text_chars,
            content_index_base=content_index_base,
            thinking_index_base=thinking_index_base,
            tool_sequence_offset_base=self.chunk_emitter.tool_sequence_offset,
            next_tool_sequence_offset=next_tool_sequence_offset,
            next_content_index_offset=next_content_index_offset,
            next_thinking_index_offset=next_thinking_index_offset,
        )

    def commit_finalized_payload(
        self,
        finalized_payload: FinalizedStreamingPayload,
        *,
        visible_text_chars: int,
        thinking_text_chars: int,
        next_tool_sequence_offset: int,
    ) -> None:
        self.chunk_emitter.tool_sequence_offset = next_tool_sequence_offset
        self.chunk_emitter.content_index_offset = finalized_payload.content_index_base + max(
            0,
            visible_text_chars,
        )
        self.chunk_emitter.thinking_index_offset = finalized_payload.thinking_index_base + max(
            0,
            thinking_text_chars,
        )


def build_cancelled_stream_outcome(
    *,
    stream_state: StreamGeneratorStateProtocol,
    cancel_reason: str | None,
) -> AgentStreamingInferenceOutcome:
    return AgentStreamingInferenceOutcome(
        payload=None,
        stream_successful=False,
        done_sent=stream_state.done_sent,
        stream_id=None,
        usage=stream_state.usage,
        tool_calls=[],
        visible_text_chars=0,
        thinking_text_chars=0,
        content_index_base=0,
        thinking_index_base=0,
        transcript=None,
        error_message=cancel_reason or "Inference cancelled.",
        error_type="cancelled",
    )
