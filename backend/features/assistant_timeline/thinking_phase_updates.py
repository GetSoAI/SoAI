"""SoAI - Shared assistant timeline thinking phase orchestration [backend/features/assistant_timeline/thinking_phase_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.thinking_phase import (
    normalize_thinking_phase_text_for_rendering,
)
from features.assistant_timeline.thinking_phase_boundary_support import (
    emit_tool_boundary_thinking_phase_for_context,
    flush_and_reconcile_visible_phase,
)
from features.assistant_timeline.thinking_phase_intermediate import (
    upsert_intermediate_thinking_phase,
)
from features.assistant_timeline.thinking_phase_state import (
    ThinkingPhaseState,
    coerce_thinking_call_id,
)

__all__ = (
    "ThinkingPhaseState",
    "coerce_thinking_call_id",
    "finalize_thinking_phase_before_tool_call",
    "upsert_intermediate_thinking_phase",
)


async def finalize_thinking_phase_before_tool_call(
    *,
    context: ChatStreamFinalizeContext,
    call_id: str,
    thinking_index_before: int,
    content_index_before: int,
    duration_ms: int | None,
    status: str,
) -> None:
    runtime = context.runtime
    stream_transcript = context.stream_transcript
    thinking_state = context.thinking_state
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        thinking_text = stream_transcript.get_thinking_text()
        boundary = max(0, min(len(thinking_text), max(0, thinking_index_before)))
        start_cursor = max(0, runtime.thinking_phase_cursor)
        should_emit_phase = boundary > start_cursor
        phase_text = thinking_text[start_cursor:boundary] if should_emit_phase else ""
        phase_text_for_emit = (
            normalize_thinking_phase_text_for_rendering(phase_text) if should_emit_phase else ""
        )
        if not should_emit_phase or not phase_text_for_emit.strip():
            await flush_and_reconcile_visible_phase(
                runtime=runtime,
                stream_transcript=stream_transcript,
                thinking_phases=context.thinking_phases,
                thinking_state=thinking_state,
                boundary=boundary,
                database_messages=context.database_messages,
                database_tool_calls=context.database_tool_calls,
                event_bus=context.event_bus,
                duration_ms=duration_ms,
                status=status,
                error_message="Thinking phase before tool boundary could not be reconciled.",
            )
            return
        await emit_tool_boundary_thinking_phase_for_context(
            context=context,
            boundary=boundary,
            content_index_before=content_index_before,
            call_id=call_id,
            phase_text_for_emit=phase_text_for_emit,
            status=status,
        )
        thinking_state.last_emit_ms = monotonic_ms()
