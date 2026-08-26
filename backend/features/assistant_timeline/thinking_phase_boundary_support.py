"""SoAI - Shared assistant timeline thinking phase boundary helpers [backend/features/assistant_timeline/thinking_phase_boundary_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.thinking_phase_anchor import (
    resolve_tool_boundary_thinking_phase_anchor,
)
from features.assistant_timeline.thinking_phase_boundary_flushing import (
    flush_existing_visible_phase,
    flush_thinking_phase_without_visible_phase,
)
from features.assistant_timeline.thinking_phase_emission import (
    build_thinking_phase_emission,
    emit_required_thinking_phase_from_parts,
)
from features.assistant_timeline.thinking_phase_state import (
    ThinkingPhaseState,
    ensure_active_thinking_phase,
)
from features.assistant_timeline.thinking_phase_upsert import (
    upsert_thinking_phase_from_identity,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversations import (
        DatabaseMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict

__all__ = (
    "emit_tool_boundary_thinking_phase",
    "emit_tool_boundary_thinking_phase_for_context",
    "flush_and_reconcile_visible_phase",
    "flush_and_reconcile_visible_phase_for_context",
)


async def emit_tool_boundary_thinking_phase(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    event_bus: EventBusProtocol,
    boundary: int,
    content_index_before: int,
    call_id: str,
    phase_text_for_emit: str,
    status: str,
) -> None:
    thinking_text = stream_transcript.get_thinking_text()
    start_cursor = max(0, runtime.thinking_phase_cursor)
    active = ensure_active_thinking_phase(
        runtime=runtime,
        stream_transcript=stream_transcript,
        thinking_phases=thinking_phases,
        thinking_state=thinking_state,
        thinking_text=thinking_text,
        end_cursor=boundary,
    )
    if active is None:
        return
    phase_id, sequence_index, anchor_type, anchor_call_id, anchor_position, started_at_ms = active
    active_start_cursor = thinking_state.active_start_cursor
    if active_start_cursor != start_cursor:
        raise ValidationError("Thinking phase state mismatch (start cursor).")
    anchor = resolve_tool_boundary_thinking_phase_anchor(
        runtime=runtime,
        call_id=call_id,
        content_index_before=content_index_before,
        prefer_before_call=True,
    )
    if sequence_index == len(thinking_phases):
        anchor_type = anchor.anchor_type
        anchor_call_id = anchor.anchor_call_id
        anchor_position = anchor.anchor_position
        thinking_state.active_anchor_type = anchor_type
        thinking_state.active_anchor_call_id = anchor_call_id
        thinking_state.active_anchor_position = anchor_position
    phase_emitted = await upsert_thinking_phase_from_identity(
        runtime=runtime,
        thinking_phases=thinking_phases,
        thinking_state=thinking_state,
        database_messages=database_messages,
        event_bus=event_bus,
        phase_identity=(
            phase_id,
            sequence_index,
            anchor_type,
            anchor_call_id,
            anchor_position,
            started_at_ms,
        ),
        phase_text=phase_text_for_emit,
        status=status,
    )
    if not phase_emitted:
        raise ValidationError("Thinking phase before tool boundary could not be emitted.")
    await flush_existing_visible_phase(
        boundary=boundary,
        database_messages=database_messages,
        database_tool_calls=database_tool_calls,
        event_bus=event_bus,
        runtime=runtime,
        stream_transcript=stream_transcript,
        thinking_state=thinking_state,
    )


async def emit_tool_boundary_thinking_phase_for_context(
    *,
    context: ChatStreamFinalizeContext,
    boundary: int,
    content_index_before: int,
    call_id: str,
    phase_text_for_emit: str,
    status: str,
) -> None:
    await emit_tool_boundary_thinking_phase(
        runtime=context.runtime,
        stream_transcript=context.stream_transcript,
        thinking_phases=context.thinking_phases,
        thinking_state=context.thinking_state,
        database_messages=context.database_messages,
        database_tool_calls=context.database_tool_calls,
        event_bus=context.event_bus,
        boundary=boundary,
        content_index_before=content_index_before,
        call_id=call_id,
        phase_text_for_emit=phase_text_for_emit,
        status=status,
    )


async def flush_and_reconcile_visible_phase(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseMessagesProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    event_bus: EventBusProtocol,
    boundary: int,
    duration_ms: int | None,
    status: str,
    error_message: str,
) -> tuple[tuple[str, int, str, str | None, int | None, int] | None, str]:
    reconciled_phase_identity: tuple[str, int, str, str | None, int | None, int] | None = None
    reconciled_phase_text = ""

    async def reconcile_visible_active_phase(
        phase_identity: tuple[str, int, str, str | None, int | None, int],
        emitted_text: str,
    ) -> None:
        nonlocal reconciled_phase_identity, reconciled_phase_text
        reconciled_phase_identity = phase_identity
        reconciled_phase_text = emitted_text
        await emit_required_thinking_phase_from_parts(
            runtime=runtime,
            thinking_phases=thinking_phases,
            thinking_state=thinking_state,
            database_messages=database_messages,
            event_bus=event_bus,
            emission=build_thinking_phase_emission(
                phase_identity=phase_identity,
                phase_text=emitted_text,
                duration_ms=duration_ms,
                status=status,
            ),
            error_message=error_message,
        )

    await flush_thinking_phase_without_visible_phase(
        boundary=boundary,
        database_messages=database_messages,
        database_tool_calls=database_tool_calls,
        event_bus=event_bus,
        runtime=runtime,
        stream_transcript=stream_transcript,
        thinking_state=thinking_state,
        on_visible_active_phase=reconcile_visible_active_phase,
        allow_existing_visible_phase=False,
    )
    return reconciled_phase_identity, reconciled_phase_text


async def flush_and_reconcile_visible_phase_for_context(
    *,
    context: ChatStreamFinalizeContext,
    boundary: int,
    duration_ms: int | None,
    status: str,
    error_message: str,
) -> tuple[tuple[str, int, str, str | None, int | None, int] | None, str]:
    return await flush_and_reconcile_visible_phase(
        runtime=context.runtime,
        stream_transcript=context.stream_transcript,
        thinking_phases=context.thinking_phases,
        thinking_state=context.thinking_state,
        database_messages=context.database_messages,
        database_tool_calls=context.database_tool_calls,
        event_bus=context.event_bus,
        boundary=boundary,
        duration_ms=duration_ms,
        status=status,
        error_message=error_message,
    )
