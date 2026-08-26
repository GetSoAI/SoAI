"""SoAI - Streaming iteration session state [backend/features/agent/runtime/streaming_iteration_session.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.validation.integers import is_strict_int
from features.agent.runtime.streaming_iteration_delivery import (
    collect_openai_stream_payload,
)
from features.openai.streaming_iteration_state import AgentStreamingIterationState

if TYPE_CHECKING:
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.streaming.protocols import StreamGeneratorStateProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from features.agent.internal_protocols import AgentToolCallsDetectedCallback
    from features.openai.streaming_iteration_state import FinalizedStreamingPayload

__all__ = ("StreamingIterationSession",)


@dataclass(slots=True)
class StreamingIterationSession:
    initial_task: Task | None
    iteration_state: AgentStreamingIterationState = field(
        default_factory=AgentStreamingIterationState,
    )
    is_first_iteration: bool = True
    pending_finalized_payload: FinalizedStreamingPayload | None = None

    def resolve_cancellation_id(self, requested_cancellation_id: str) -> str:
        if not self.is_first_iteration:
            return requested_cancellation_id
        if self.initial_task is None:
            return requested_cancellation_id
        task_cancellation_id = self.initial_task.cancellation_id
        if task_cancellation_id.strip():
            return task_cancellation_id.strip()
        return requested_cancellation_id

    def claim_initial_task(self) -> Task | None:
        if not self.is_first_iteration:
            return None
        self.is_first_iteration = False
        return self.initial_task

    async def collect_payload(
        self,
        stream_generator: AsyncIterator[bytes],
        stream_transcript: OpenAIStreamTranscript,
        stream_state: StreamGeneratorStateProtocol,
        on_bytes: Callable[[bytes], Awaitable[None] | None],
        on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None] | None] | None,
        on_tool_calls_detected: AgentToolCallsDetectedCallback | None,
        should_skip_error_chunk: Callable[[tuple[str, str]], Awaitable[bool]],
    ) -> tuple[FinalizedStreamingPayload, tuple[str, str] | None]:
        finalized_payload, captured_error = await collect_openai_stream_payload(
            stream_generator,
            self.iteration_state,
            stream_transcript,
            stream_state,
            on_bytes,
            on_visible_deltas,
            on_tool_calls_detected,
            should_skip_error_chunk,
        )
        self.pending_finalized_payload = finalized_payload
        return finalized_payload, captured_error

    def commit_pending_finalized_payload(
        self,
        *,
        visible_text_chars: int,
        thinking_text_chars: int,
        tool_calls: list[JSONDict],
    ) -> None:
        finalized_payload = self.pending_finalized_payload
        if finalized_payload is None:
            return
        self.iteration_state.commit_finalized_payload(
            finalized_payload,
            visible_text_chars=visible_text_chars,
            thinking_text_chars=thinking_text_chars,
            next_tool_sequence_offset=_resolve_next_tool_sequence_offset(
                finalized_payload.tool_sequence_offset_base,
                finalized_payload.next_tool_sequence_offset,
                tool_calls,
            ),
        )
        self.pending_finalized_payload = None

    def discard_pending_finalized_payload(self) -> None:
        self.pending_finalized_payload = None


def _resolve_next_tool_sequence_offset(
    base_offset: int,
    fallback_offset: int,
    tool_calls: list[JSONDict],
) -> int:
    if not tool_calls:
        return base_offset
    next_offset = base_offset
    for tool_call in tool_calls:
        sequence_index = tool_call.get("sequence_index")
        if is_strict_int(sequence_index):
            next_offset = max(next_offset, int(sequence_index) + 1)
    return max(next_offset, fallback_offset) if next_offset == base_offset else next_offset
