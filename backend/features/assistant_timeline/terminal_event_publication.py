"""SoAI - Durable assistant timeline terminal event publication [backend/features/assistant_timeline/terminal_event_publication.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import run_idempotent_current_task_operation
from core.conversations.assistant_terminal_finalization import (
    TerminalAssistantMessageFinalization,
)
from core.conversations.streaming_assistant_terminal_commit import (
    StreamingAssistantTerminalCommitRequest,
)
from core.timing.epoch import epoch_ms
from features.assistant_timeline.message_write_versions import (
    record_assistant_timeline_message_write,
)
from features.assistant_timeline.models import PendingAssistantMessageEvent
from features.assistant_timeline.publish import (
    run_chat_stream_event_operation_locked,
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
    "build_cancelled_assistant_finalization",
    "persist_and_publish_terminal_chat_stream_event",
)


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


def _record_terminal_message_state(
    *,
    runtime: AssistantTimelineRuntime,
    finalization: TerminalAssistantMessageFinalization,
) -> None:
    if runtime.input_finalization is not None:
        if finalization.finish_reason == "cancelled":
            runtime.input_terminal_state = "cancelled"
        elif finalization.finish_reason == "error":
            runtime.input_terminal_state = "failed"
        else:
            runtime.input_terminal_state = "completed"
        runtime.input_terminal_code = finalization.terminal_code


def _build_terminal_commit_request(
    *,
    runtime: AssistantTimelineRuntime,
    terminal_event: PendingAssistantMessageEvent,
    finalization: TerminalAssistantMessageFinalization,
) -> StreamingAssistantTerminalCommitRequest:
    events = tuple(
        (
            entry.sequence,
            entry.assistant_revision,
            entry.event_type,
            dict(entry.payload),
            entry.created_at,
        )
        for entry in (*runtime.assistant_event_buffer, terminal_event)
    )
    return StreamingAssistantTerminalCommitRequest(
        conv_id=runtime.conv_id,
        user_id=runtime.user_id,
        assistant_at_ms=runtime.assistant_at_ms,
        request_id=runtime.request_id,
        content_text=runtime.assistant_visible_text,
        events=events,
        finalization=finalization,
        input_finalization=runtime.input_finalization,
    )


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
        terminal_event = PendingAssistantMessageEvent(
            sequence=sequence,
            assistant_revision=assistant_revision,
            event_type=event_type,
            payload=dict(stamped_payload),
            created_at=epoch_ms(),
        )
        if runtime.assistant_placeholder_persisted:
            runtime.terminal_persistence_attempted = True
            await runtime.require_mutation_allowed()
            terminal_request = _build_terminal_commit_request(
                runtime=runtime,
                terminal_event=terminal_event,
                finalization=finalization,
            )
            write_result = await run_idempotent_current_task_operation(
                lambda: database_messages.commit_streaming_assistant_terminal(
                    terminal_request,
                ),
            )
            record_assistant_timeline_message_write(runtime, write_result)
            runtime.assistant_event_buffer.clear()
            _record_terminal_message_state(runtime=runtime, finalization=finalization)
        else:
            runtime.assistant_event_buffer.append(terminal_event)
        runtime.next_sequence = sequence + 1
        runtime.assistant_revision = assistant_revision
        runtime.terminal_event_emitted = True
        runtime.terminal_persistence_completed = True

    chat_stream_event = await run_chat_stream_event_operation_locked(
        runtime=runtime,
        event_type=event_type,
        payload=payload,
        locked_operation=locked_operation,
    )
    await event_bus.publish(chat_stream_event)
    runtime.terminal_event_published = True
