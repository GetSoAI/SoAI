"""SoAI - Shared assistant timeline finalization support [backend/features/assistant_timeline/stream_finalize_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.assistant_timeline.assistant_text import (
    flush_streaming_assistant_content_if_due_locked,
    persist_and_publish_assistant_text_delta_locked,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock
from features.assistant_timeline.terminal_visible_text import (
    drain_terminal_visible_text,
)
from features.assistant_timeline.tool_call_terminal_event_synthesis import (
    synthesize_terminal_tool_call_events,
)
from features.assistant_timeline.tool_events_flushing import flush_pending_tool_events

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tool_calls.protocols import DatabaseToolCallsProtocol

__all__ = (
    "finalize_terminal_tool_events",
    "flush_pending_visible_text_deltas",
)


async def flush_pending_visible_text_deltas(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
    pending_visible_text: str | None = None,
) -> None:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        resolved_pending_visible_text = pending_visible_text
        if resolved_pending_visible_text is None:
            resolved_pending_visible_text = drain_terminal_visible_text(
                runtime=runtime,
                stream_transcript=stream_transcript,
            )
        await persist_and_publish_assistant_text_delta_locked(
            runtime=runtime,
            delta_text=resolved_pending_visible_text,
            database_messages=database_messages,
            event_bus=event_bus,
            force_publish=True,
            allow_terminal_finalization=True,
        )
        await flush_streaming_assistant_content_if_due_locked(
            runtime=runtime,
            database_messages=database_messages,
            force=True,
        )


async def finalize_terminal_tool_events(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseStreamingMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    task_registry: TaskRegistryLifecycleView,
    status: str,
    message: str,
) -> None:
    await flush_pending_tool_events(
        event_bus=event_bus,
        runtime=runtime,
        database_messages=database_messages,
        database_tool_calls=database_tool_calls,
    )
    await synthesize_terminal_tool_call_events(
        runtime=runtime,
        event_bus=event_bus,
        database_messages=database_messages,
        database_tool_calls=database_tool_calls,
        task_registry=task_registry,
        status=status,
        message=message,
        preserve_active_owned_tool_calls=False,
    )
