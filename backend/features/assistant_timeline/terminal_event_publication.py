"""SoAI - Durable assistant timeline terminal event publication [backend/features/assistant_timeline/terminal_event_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.message_write_versions import (
    record_assistant_timeline_message_write,
)
from features.assistant_timeline.models import PendingAssistantMessageEvent
from features.assistant_timeline.publish import (
    run_chat_stream_event_operation_locked,
)
from features.assistant_timeline.publish_persistence import (
    flush_assistant_event_buffer_locked,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.events.types_system import ChatStreamEvent
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "TerminalAssistantMessageFinalization",
    "build_cancelled_assistant_finalization",
    "persist_and_publish_terminal_chat_stream_event",
)


@dataclass(frozen=True, slots=True)
class TerminalAssistantMessageFinalization:
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    usage_source: str | None
    generation_latency_ms: int | None
    thinking_tail_duration_ms: int | None
    terminal_reason: str | None
    terminal_code: str


def build_cancelled_assistant_finalization(
    *,
    duration_ms: int,
    thinking_tail_duration_ms: int,
    reason: str,
    code: str,
) -> TerminalAssistantMessageFinalization:
    return TerminalAssistantMessageFinalization(
        finish_reason="cancelled",
        prompt_tokens=None,
        completion_tokens=None,
        total_tokens=None,
        usage_source=None,
        generation_latency_ms=duration_ms,
        thinking_tail_duration_ms=thinking_tail_duration_ms,
        terminal_reason=reason,
        terminal_code=code,
    )


async def _flush_all_buffered_events_locked(
    *,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
) -> None:
    if not runtime.assistant_placeholder_persisted:
        return
    while runtime.assistant_event_buffer:
        did_flush = await flush_assistant_event_buffer_locked(
            runtime,
            database_messages,
            now_ms=monotonic_ms(),
            force=True,
        )
        if not did_flush:
            raise StateError("Assistant terminal event buffer flush made no progress.")


async def _finalize_assistant_message(
    *,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    finalization: TerminalAssistantMessageFinalization,
) -> None:
    if not runtime.assistant_placeholder_persisted:
        return
    await runtime.require_mutation_allowed()
    write_result = await database_messages.finalize_streaming_assistant_message(
        runtime.conv_id,
        runtime.user_id,
        created_at_ms=runtime.assistant_at_ms,
        request_id=runtime.request_id,
        finish_reason=finalization.finish_reason,
        prompt_tokens=finalization.prompt_tokens,
        completion_tokens=finalization.completion_tokens,
        total_tokens=finalization.total_tokens,
        usage_source=finalization.usage_source,
        generation_latency_ms=finalization.generation_latency_ms,
        thinking_tail_duration_ms=finalization.thinking_tail_duration_ms,
        terminal_reason=finalization.terminal_reason,
        input_finalization=runtime.input_finalization,
        input_terminal_code=finalization.terminal_code,
    )
    record_assistant_timeline_message_write(runtime, write_result)
    if runtime.input_finalization is not None:
        if finalization.finish_reason == "cancelled":
            runtime.input_terminal_state = "cancelled"
        elif finalization.finish_reason == "error":
            runtime.input_terminal_state = "failed"
        else:
            runtime.input_terminal_state = "completed"
        runtime.input_terminal_code = finalization.terminal_code


async def persist_and_publish_terminal_chat_stream_event(
    *,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_type: str,
    payload: JSONDict,
    finalization: TerminalAssistantMessageFinalization,
) -> None:
    async def locked_operation(
        sequence: int,
        assistant_revision: int,
        stamped_payload: JSONDict,
        _chat_stream_event: ChatStreamEvent,
    ) -> None:
        runtime.assistant_event_buffer.append(
            PendingAssistantMessageEvent(
                sequence=sequence,
                assistant_revision=assistant_revision,
                event_type=event_type,
                payload=dict(stamped_payload),
                created_at=epoch_ms(),
            ),
        )
        runtime.next_sequence = sequence + 1
        runtime.assistant_revision = assistant_revision
        await _flush_all_buffered_events_locked(
            runtime=runtime,
            database_messages=database_messages,
        )
        await _finalize_assistant_message(
            runtime=runtime,
            database_messages=database_messages,
            finalization=finalization,
        )
        runtime.terminal_event_emitted = True
        runtime.terminal_event_published = True
        runtime.terminal_persistence_completed = True

    chat_stream_event = await run_chat_stream_event_operation_locked(
        runtime=runtime,
        event_type=event_type,
        payload=payload,
        locked_operation=locked_operation,
    )
    await event_bus.publish(chat_stream_event)
