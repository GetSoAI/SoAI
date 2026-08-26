"""SoAI - Shared assistant timeline intermediate thinking phase upsert [backend/features/assistant_timeline/thinking_phase_intermediate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock
from features.assistant_timeline.thinking_phase_emission import (
    build_thinking_phase_emission,
    emit_thinking_phase_from_parts,
)
from features.assistant_timeline.thinking_phase_state import (
    ThinkingPhaseState,
    resolve_active_thinking_phase_identity,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.types.json import JSONDict

__all__ = ("upsert_intermediate_thinking_phase",)

_THINKING_STREAM_MIN_CHARS: int = 96
_THINKING_STREAM_MAX_DELAY_MS: int = 250


async def upsert_intermediate_thinking_phase(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
) -> None:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        thinking_text = stream_transcript.get_thinking_text()
        if not thinking_text:
            return
        end_cursor = len(thinking_text)
        active = resolve_active_thinking_phase_identity(
            runtime=runtime,
            stream_transcript=stream_transcript,
            thinking_phases=thinking_phases,
            thinking_state=thinking_state,
            thinking_text=thinking_text,
            end_cursor=end_cursor,
            operation="assistant_timeline.upsert_intermediate_thinking_phase",
        )
        if active is None:
            return
        start_cursor = thinking_state.active_start_cursor
        if start_cursor is None:
            raise ValidationError("Thinking phase state is invalid (missing start cursor).")
        if end_cursor <= start_cursor:
            return
        phase_text = thinking_text[start_cursor:end_cursor]
        now_ms = monotonic_ms()
        emitted_chars = max(0, thinking_state.active_last_emitted_chars)
        available_chars = max(0, len(phase_text) - emitted_chars)
        if emitted_chars > 0:
            elapsed_ms = now_ms - thinking_state.last_emit_ms if thinking_state.last_emit_ms else 0
            if (
                available_chars < _THINKING_STREAM_MIN_CHARS
                and elapsed_ms < _THINKING_STREAM_MAX_DELAY_MS
            ):
                return
        await emit_thinking_phase_from_parts(
            runtime=runtime,
            thinking_phases=thinking_phases,
            thinking_state=thinking_state,
            database_messages=database_messages,
            event_bus=event_bus,
            emission=build_thinking_phase_emission(
                phase_identity=active,
                phase_text=phase_text,
                duration_ms=None,
                status="running",
                emitted_at_ms=now_ms,
                set_active_last_emitted_chars=True,
            ),
        )
