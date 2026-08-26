"""SoAI - Shared assistant timeline finalization context [backend/features/assistant_timeline/stream_finalize_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from features.assistant_timeline.models import AssistantTimelineRuntime

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversations import (
        DatabaseMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.tasks.protocols import TaskRegistryLifecycleView
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict
    from features.assistant_timeline.thinking_phase_state import (
        ThinkingPhaseState,
    )

__all__ = (
    "ChatStreamFinalizeContext",
    "build_chat_stream_finalize_context",
)


@dataclass(frozen=True, slots=True)
class ChatStreamFinalizeContext:
    runtime: AssistantTimelineRuntime
    stream_transcript: OpenAIStreamTranscript
    thinking_phases: list[JSONDict]
    thinking_state: ThinkingPhaseState
    database_messages: DatabaseMessagesProtocol
    database_tool_calls: DatabaseToolCallsProtocol
    task_registry: TaskRegistryLifecycleView
    event_bus: EventBusProtocol


def build_chat_stream_finalize_context(
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    task_registry: TaskRegistryLifecycleView,
    event_bus: EventBusProtocol,
) -> ChatStreamFinalizeContext:
    return ChatStreamFinalizeContext(
        runtime=runtime,
        stream_transcript=stream_transcript,
        thinking_phases=thinking_phases,
        thinking_state=thinking_state,
        database_messages=database_messages,
        database_tool_calls=database_tool_calls,
        task_registry=task_registry,
        event_bus=event_bus,
    )
