"""SoAI - Shared assistant timeline thinking tail finalization [backend/features/assistant_timeline/thinking_phase_tail_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.thinking_phase import (
    normalize_thinking_phase_text_for_rendering,
)
from features.assistant_timeline.thinking_phase_boundary_flushing import (
    flush_existing_visible_phase_for_context,
)
from features.assistant_timeline.thinking_phase_boundary_support import (
    flush_and_reconcile_visible_phase_for_context,
)
from features.assistant_timeline.thinking_phase_emission import (
    build_thinking_phase_emission,
    build_thinking_phase_emission_context_for_finalize_context,
    emit_required_thinking_phase,
)
from features.assistant_timeline.thinking_phase_state import (
    require_active_thinking_phase_identity,
)

__all__ = ("finalize_thinking_tail_phase_for_context",)


async def finalize_thinking_tail_phase_for_context(
    *,
    context: ChatStreamFinalizeContext,
    status: str,
) -> int:
    runtime = context.runtime
    stream_transcript = context.stream_transcript
    thinking_state = context.thinking_state
    lock = ensure_chat_stream_publish_lock(runtime)
    tail_duration_ms = 0
    async with lock:
        thinking_text = stream_transcript.get_thinking_text()
        raw_tail_duration_ms = stream_transcript.get_thinking_tail_duration_ms()
        tail_duration_ms = (
            raw_tail_duration_ms
            if isinstance(raw_tail_duration_ms, int) and raw_tail_duration_ms >= 0
            else 0
        )
        end_cursor = len(thinking_text)
        start_cursor = max(0, runtime.thinking_phase_cursor)
        tail_phase_text = (
            thinking_text[start_cursor:end_cursor] if end_cursor > start_cursor else ""
        )
        tail_phase_text_for_emit = (
            normalize_thinking_phase_text_for_rendering(tail_phase_text) if tail_phase_text else ""
        )
        if not tail_phase_text_for_emit.strip():
            await _flush_tail_without_new_visible_phase(
                context=context,
                boundary=end_cursor,
                duration_ms=tail_duration_ms,
                status=status,
            )
            return tail_duration_ms
        active = require_active_thinking_phase_identity(
            runtime=runtime,
            stream_transcript=stream_transcript,
            thinking_phases=context.thinking_phases,
            thinking_state=thinking_state,
            thinking_text=thinking_text,
            end_cursor=end_cursor,
            operation="assistant_timeline.finalize_thinking_tail_phase",
            error_message="Thinking tail phase identity could not be resolved.",
        )
        active_start_cursor = thinking_state.active_start_cursor
        if active_start_cursor != start_cursor:
            raise ValidationError("Thinking phase state mismatch (start cursor).")
        await emit_required_thinking_phase(
            context=build_thinking_phase_emission_context_for_finalize_context(context),
            emission=build_thinking_phase_emission(
                phase_identity=active,
                phase_text=tail_phase_text_for_emit,
                duration_ms=tail_duration_ms,
                status=status,
            ),
            error_message="Thinking tail phase could not be emitted.",
        )
        await flush_existing_visible_phase_for_context(
            context=context,
            boundary=end_cursor,
        )
    return tail_duration_ms


async def _flush_tail_without_new_visible_phase(
    *,
    context: ChatStreamFinalizeContext,
    boundary: int,
    duration_ms: int,
    status: str,
) -> None:
    await flush_and_reconcile_visible_phase_for_context(
        context=context,
        boundary=boundary,
        duration_ms=duration_ms,
        status=status,
        error_message="Thinking tail phase could not be reconciled.",
    )
