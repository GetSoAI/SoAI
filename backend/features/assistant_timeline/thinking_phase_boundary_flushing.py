"""SoAI - Shared assistant timeline thinking phase boundary flushing [backend/features/assistant_timeline/thinking_phase_boundary_flushing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.thinking_phase_state import (
    ThinkingPhaseState,
    advance_thinking_phase_cursor,
)
from features.assistant_timeline.tool_events_flushing import (
    flush_pending_tool_events_locked,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversations import (
        DatabaseMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.tool_calls.protocols import DatabaseToolCallsProtocol

__all__ = (
    "flush_existing_visible_phase",
    "flush_existing_visible_phase_for_context",
    "flush_thinking_phase_without_visible_phase",
)


async def flush_thinking_phase_without_visible_phase(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    event_bus: EventBusProtocol,
    boundary: int,
    on_visible_active_phase: (
        Callable[[tuple[str, int, str, str | None, int | None, int], str], Awaitable[None] | None]
        | None
    ) = None,
    allow_existing_visible_phase: bool = False,
) -> None:
    await advance_thinking_phase_cursor(
        runtime=runtime,
        stream_transcript=stream_transcript,
        thinking_state=thinking_state,
        boundary=boundary,
        on_visible_active_phase=on_visible_active_phase,
        allow_existing_visible_phase=allow_existing_visible_phase,
    )
    await flush_pending_tool_events_locked(
        event_bus=event_bus,
        runtime=runtime,
        database_messages=database_messages,
        database_tool_calls=database_tool_calls,
    )


async def flush_existing_visible_phase(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    event_bus: EventBusProtocol,
    boundary: int,
) -> None:
    await flush_thinking_phase_without_visible_phase(
        runtime=runtime,
        stream_transcript=stream_transcript,
        thinking_state=thinking_state,
        database_messages=database_messages,
        database_tool_calls=database_tool_calls,
        event_bus=event_bus,
        boundary=boundary,
        allow_existing_visible_phase=True,
    )


async def flush_existing_visible_phase_for_context(
    *,
    context: ChatStreamFinalizeContext,
    boundary: int,
) -> None:
    await flush_existing_visible_phase(
        runtime=context.runtime,
        stream_transcript=context.stream_transcript,
        thinking_state=context.thinking_state,
        database_messages=context.database_messages,
        database_tool_calls=context.database_tool_calls,
        event_bus=context.event_bus,
        boundary=boundary,
    )
