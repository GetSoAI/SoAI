"""SoAI - Shared assistant timeline session orchestration [backend/features/assistant_timeline/assistant_timeline_session.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from core.concurrency.wait_race import WaitRaceOutcome, wait_for_awaitable_or_event
from core.di.validation import require_dependencies
from core.errors.exceptions import StateError
from core.openai.sse_chunk_decoding import decode_sse_chunk_bytes
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from features.assistant_timeline.activity_ticker_tasks import (
    take_activity_ticker_exception,
)
from features.assistant_timeline.assistant_timeline_shutdown import (
    stop_timeline_session_tickers,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.processing_activity import (
    start_processing_activity_ticker,
)
from features.assistant_timeline.status_preview_scheduler import (
    start_status_preview_scheduler,
)
from features.assistant_timeline.stream_chunk_processing import process_stream_chunk
from features.assistant_timeline.stream_generator_cleanup import (
    cancel_assistant_stream_generator,
    close_assistant_stream_generator,
)
from features.assistant_timeline.thinking_phase_updates import (
    ThinkingPhaseState,
)
from features.assistant_timeline.tool_events_subscription import (
    subscribe_tool_events_for_stream,
)
from features.assistant_timeline.wait_for_user_activity import (
    start_wait_for_user_activity_ticker,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversations import (
        DatabaseMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict
    from features.assistant_timeline.models import (
        StatusPreviewRequest,
        StatusPreviewResult,
    )

__all__ = ("AssistantTimelineSession",)

_STREAM_OUTPUT_CONTRACT_ERROR = "OpenAI stream generator yielded a non-bytes chunk."


@dataclass(slots=True)
class AssistantTimelineSession:
    runtime: AssistantTimelineRuntime
    event_bus: EventBusProtocol
    database_messages: DatabaseMessagesProtocol
    database_tool_calls: DatabaseToolCallsProtocol
    task_registry: TaskRegistryLifecycleView
    task_registry_queries: TaskRegistryQueryView
    track_background_task: Callable[[asyncio.Task[None]], None]
    prompt_token_counter: PromptTokenCounter
    status_preview_executor: (
        Callable[
            [StatusPreviewRequest],
            Awaitable[StatusPreviewResult | None],
        ]
        | None
    ) = None
    collect_tool_calls: bool = True
    stream_transcript: OpenAIStreamTranscript = field(init=False)
    thinking_phases: list[JSONDict] = field(init=False)
    thinking_state: ThinkingPhaseState = field(init=False)
    wait_for_user_tick_task: asyncio.Task[None] | None = field(default=None, init=False)
    processing_tick_task: asyncio.Task[None] | None = field(default=None, init=False)
    status_preview_tick_task: asyncio.Task[None] | None = field(default=None, init=False)
    _unsubscribe: Callable[[], None] = field(default=lambda: None, init=False)

    def __post_init__(self) -> None:
        require_dependencies(
            owner="AssistantTimelineSession",
            runtime=self.runtime,
            event_bus=self.event_bus,
            database_messages=self.database_messages,
            database_tool_calls=self.database_tool_calls,
            task_registry=self.task_registry,
            task_registry_queries=self.task_registry_queries,
            track_background_task=self.track_background_task,
            prompt_token_counter=self.prompt_token_counter,
        )
        runtime = self.runtime
        runtime.detach_event = runtime.detach_event or asyncio.Event()
        self.stream_transcript = OpenAIStreamTranscript(
            model_hint=runtime.model_id,
            collect_tool_calls=self.collect_tool_calls,
        )
        self.thinking_phases = []
        runtime.thinking_phases = self.thinking_phases
        self.thinking_state = ThinkingPhaseState(
            message_identity=f"thinking:{runtime.conv_id}:{runtime.assistant_at_ms}",
        )

    def start(self) -> None:
        _, self._unsubscribe = subscribe_tool_events_for_stream(
            event_bus=self.event_bus,
            runtime=self.runtime,
            database_messages=self.database_messages,
            database_tool_calls=self.database_tool_calls,
        )
        self.wait_for_user_tick_task = start_wait_for_user_activity_ticker(
            runtime=self.runtime,
            event_bus=self.event_bus,
            database_messages=self.database_messages,
            task_registry_queries=self.task_registry_queries,
            track_background_task=self.track_background_task,
        )
        self.processing_tick_task = start_processing_activity_ticker(
            runtime=self.runtime,
            event_bus=self.event_bus,
            database_messages=self.database_messages,
            track_background_task=self.track_background_task,
        )
        self.status_preview_tick_task = start_status_preview_scheduler(
            runtime=self.runtime,
            event_bus=self.event_bus,
            track_background_task=self.track_background_task,
            preview_executor=self.status_preview_executor,
        )

    async def consume_stream(self, stream_generator: AsyncGenerator[bytes]) -> None:
        stream_generator_closed = False
        try:
            while True:
                self.wait_for_user_tick_task, wait_exception = take_activity_ticker_exception(
                    self.wait_for_user_tick_task,
                )
                if wait_exception is not None:
                    raise StateError("Wait-for-user activity ticker exited unexpectedly.")
                self.processing_tick_task, processing_exception = take_activity_ticker_exception(
                    self.processing_tick_task,
                )
                if processing_exception is not None:
                    raise StateError("Processing activity ticker exited unexpectedly.")
                self.status_preview_tick_task, status_preview_exception = (
                    take_activity_ticker_exception(self.status_preview_tick_task)
                )
                if status_preview_exception is not None:
                    raise StateError("Status preview scheduler exited unexpectedly.")
                detach_event = self.runtime.detach_event
                if detach_event is not None and detach_event.is_set():
                    stream_generator_closed = await cancel_assistant_stream_generator(
                        stream_generator,
                        stream_generator_closed=stream_generator_closed,
                    )
                    return
                if detach_event is None:
                    try:
                        chunk: bytes | None = await anext(stream_generator)
                    except StopAsyncIteration:
                        stream_generator_closed = True
                        return
                else:
                    try:
                        race_result = await wait_for_awaitable_or_event(
                            anext(stream_generator),
                            detach_event,
                        )
                    except StopAsyncIteration:
                        stream_generator_closed = True
                        return
                    if race_result.outcome is WaitRaceOutcome.EVENT_TRIGGERED:
                        stream_generator_closed = await cancel_assistant_stream_generator(
                            stream_generator,
                            stream_generator_closed=stream_generator_closed,
                        )
                        return
                    chunk = self._require_stream_chunk_bytes(race_result.value)
                detach_event = self.runtime.detach_event
                if detach_event is not None and detach_event.is_set():
                    stream_generator_closed = await cancel_assistant_stream_generator(
                        stream_generator,
                        stream_generator_closed=stream_generator_closed,
                    )
                    return
                chunk = self._require_stream_chunk_bytes(chunk)
                keep_running = await self.consume_chunk(chunk)
                if not keep_running:
                    stream_generator_closed = await close_assistant_stream_generator(
                        stream_generator,
                        stream_generator_closed=stream_generator_closed,
                    )
                    return
        except asyncio.CancelledError:
            await cancel_assistant_stream_generator(
                stream_generator,
                stream_generator_closed=stream_generator_closed,
            )
            raise
        finally:
            if not stream_generator_closed:
                await cancel_assistant_stream_generator(
                    stream_generator,
                    stream_generator_closed=stream_generator_closed,
                )

    def _require_stream_chunk_bytes(
        self,
        chunk: bytes | bytearray | memoryview | None,
    ) -> bytes:
        if not isinstance(chunk, bytes):
            raise StateError(_STREAM_OUTPUT_CONTRACT_ERROR)
        return chunk

    async def consume_chunk(self, chunk: bytes) -> bool:
        decoded_chunk = decode_sse_chunk_bytes(chunk)
        if decoded_chunk is None:
            return True
        return await process_stream_chunk(
            decoded_chunk=decoded_chunk,
            runtime=self.runtime,
            stream_transcript=self.stream_transcript,
            prompt_token_counter=self.prompt_token_counter,
            thinking_phases=self.thinking_phases,
            thinking_state=self.thinking_state,
            database_messages=self.database_messages,
            database_tool_calls=self.database_tool_calls,
            task_registry=self.task_registry,
            event_bus=self.event_bus,
        )

    async def close(self) -> None:
        try:
            if not self.runtime.post_terminal_tool_call_ids:
                self._unsubscribe()
        finally:
            await stop_timeline_session_tickers(self)
