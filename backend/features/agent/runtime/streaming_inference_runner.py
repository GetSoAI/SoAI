"""SoAI - Shared streaming inference runner core [backend/features/agent/runtime/streaming_inference_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from core.errors.exceptions import StateError
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.runtime.request_context import RequestContext
from features.agent.internal_protocols import (
    AgentStreamingInferenceOutcome,
    AgentStreamingInferenceRunnerProtocol,
)
from features.agent.runtime.streaming_iteration_session import StreamingIterationSession
from features.agent.runtime.types import StreamingRunnerCallbackBases
from features.api.streaming.stream_generator_state import StreamGeneratorState
from features.openai.streaming_iteration_state import build_cancelled_stream_outcome

if TYPE_CHECKING:
    from core.events.types_base import Event
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from features.agent.internal_protocols import AgentToolCallsDetectedCallback

__all__ = (
    "INFERENCE_ADMISSION_UNAVAILABLE_ERROR_TYPE",
    "StreamingInferenceRunner",
    "StreamingInferenceRunnerCallbacks",
    "StreamingTaskCreationAbortedError",
    "StreamingTaskCreationRetryableError",
)

INFERENCE_ADMISSION_UNAVAILABLE_ERROR_TYPE: str = "inference_admission_unavailable"


class StreamingTaskCreationAbortedError(Exception):
    outcome: AgentStreamingInferenceOutcome

    def __init__(self, outcome: AgentStreamingInferenceOutcome) -> None:
        super().__init__("Streaming inference task creation aborted.")
        self.outcome = outcome


class StreamingTaskCreationRetryableError(Exception):
    error_message: str
    error_type: str

    def __init__(self, *, error_message: str, error_type: str) -> None:
        normalized_message = str(error_message or "").strip()
        normalized_type = str(error_type or "").strip()
        super().__init__(
            normalized_message or "Streaming inference task creation retryable failure.",
        )
        self.error_message = normalized_message
        self.error_type = normalized_type or "server_error"

    @override
    def __str__(self) -> str:
        return str(self.args[0]) if self.args else ""

    def __getnewargs_ex__(self) -> tuple[tuple[()], dict[str, str]]:
        return ((), {"error_message": self.error_message, "error_type": self.error_type})


@dataclass(frozen=True, slots=True)
class StreamingInferenceRunnerCallbacks(StreamingRunnerCallbackBases):
    build_context: Callable[[RequestContext, str, int, str | None], RequestContext]
    create_stream_transcript: Callable[[Task], OpenAIStreamTranscript]
    on_task_ready: Callable[[Task, int], Awaitable[None] | None] | None
    should_skip_error_chunk: Callable[[str, tuple[str, str]], Awaitable[bool]]
    read_cancel_state: Callable[[str], Awaitable[tuple[bool, str | None]]]
    resolve_stream_id: Callable[[StreamingIterationSession, JSONDict | None], str | None]


@dataclass(slots=True)
class StreamingInferenceRunner(AgentStreamingInferenceRunnerProtocol):
    context: RequestContext
    initial_task: Task | None
    initial_reply_queue: asyncio.Queue[Event] | None
    callbacks: StreamingInferenceRunnerCallbacks
    iteration_session: StreamingIterationSession = field(init=False)

    def __post_init__(self) -> None:
        if (self.initial_task is None) != (self.initial_reply_queue is None):
            raise StateError("Initial streaming task and reply queue must both be present.")
        self.iteration_session = StreamingIterationSession(initial_task=self.initial_task)

    @override
    def reserve_tool_sequence_indexes(self, count: int) -> None:
        if count <= 0:
            return
        self.iteration_session.iteration_state.chunk_emitter.tool_sequence_offset += int(count)

    @override
    def commit_latest_iteration(
        self,
        *,
        visible_text_chars: int,
        thinking_text_chars: int,
        tool_calls: list[JSONDict],
    ) -> None:
        self.iteration_session.commit_pending_finalized_payload(
            visible_text_chars=visible_text_chars,
            thinking_text_chars=thinking_text_chars,
            tool_calls=tool_calls,
        )

    @override
    def discard_latest_iteration(self) -> None:
        self.iteration_session.discard_pending_finalized_payload()

    @override
    async def __call__(
        self,
        payload: JSONDict,
        *,
        iteration_index: int,
        cancellation_id: str,
        on_bytes: Callable[[bytes], Awaitable[None] | None],
        on_visible_deltas: Callable[[tuple[str, ...]], Awaitable[None] | None] | None = None,
        on_tool_calls_detected: AgentToolCallsDetectedCallback | None = None,
    ) -> AgentStreamingInferenceOutcome:
        effective_cancellation_id = self.iteration_session.resolve_cancellation_id(cancellation_id)
        iteration_context = self.callbacks.build_context(
            self.context,
            effective_cancellation_id,
            iteration_index,
            None,
        )
        try:
            initial_task = self.iteration_session.claim_initial_task()
            if initial_task is not None:
                iteration_task = initial_task
                if self.initial_reply_queue is None:
                    raise StateError("Initial streaming reply queue is unavailable.")
                reply_queue = self.initial_reply_queue
            else:
                iteration_task, reply_queue = await self.callbacks.create_additional_task(
                    payload,
                    iteration_context,
                    effective_cancellation_id,
                    on_bytes,
                )
        except StreamingTaskCreationAbortedError as exception:
            return exception.outcome
        if self.callbacks.on_task_ready is not None:
            maybe_awaitable = self.callbacks.on_task_ready(iteration_task, iteration_index)
            if maybe_awaitable is not None:
                await maybe_awaitable
        stream_context = self.callbacks.build_context(
            self.context,
            effective_cancellation_id,
            iteration_index,
            iteration_task.task_id,
        )
        stream_state = StreamGeneratorState()
        stream_transcript = self.callbacks.create_stream_transcript(iteration_task)
        stream_generator = self.callbacks.create_stream_generator(
            reply_queue,
            stream_context,
            iteration_task,
            stream_state,
            stream_transcript,
        )

        async def should_skip_error_chunk(parsed_error: tuple[str, str]) -> bool:
            return await self.callbacks.should_skip_error_chunk(
                effective_cancellation_id,
                parsed_error,
            )

        finalized_payload, captured_error = await self.iteration_session.collect_payload(
            stream_generator,
            stream_transcript,
            stream_state,
            on_bytes,
            on_visible_deltas,
            on_tool_calls_detected,
            should_skip_error_chunk,
        )
        cancelled, cancel_reason = await self.callbacks.read_cancel_state(effective_cancellation_id)
        if cancelled:
            self.discard_latest_iteration()
            return build_cancelled_stream_outcome(
                stream_state=stream_state,
                cancel_reason=cancel_reason,
            )
        error_message: str | None = None
        error_type: str | None = None
        if not stream_state.stream_successful:
            if captured_error is not None:
                error_message, error_type = captured_error
            else:
                error_message = "Streaming inference failed."
                error_type = "server_error"
        return AgentStreamingInferenceOutcome(
            payload=finalized_payload.payload,
            stream_successful=bool(stream_state.stream_successful),
            done_sent=stream_state.done_sent,
            stream_id=self.callbacks.resolve_stream_id(
                self.iteration_session,
                finalized_payload.payload,
            ),
            usage=stream_state.usage,
            tool_calls=finalized_payload.tool_calls,
            visible_text_chars=finalized_payload.visible_text_chars,
            thinking_text_chars=finalized_payload.thinking_text_chars,
            content_index_base=finalized_payload.content_index_base,
            thinking_index_base=finalized_payload.thinking_index_base,
            transcript=stream_transcript,
            error_message=error_message,
            error_type=error_type,
        )
