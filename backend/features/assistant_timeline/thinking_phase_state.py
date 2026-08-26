"""SoAI - Shared assistant timeline thinking phase state helpers [backend/features/assistant_timeline/thinking_phase_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.timing.epoch import epoch_ms
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.thinking_phase import (
    normalize_thinking_phase_text_for_rendering,
)
from features.assistant_timeline.thinking_phase_anchor import (
    resolve_new_thinking_phase_anchor,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ThinkingPhaseState",
    "advance_thinking_phase_cursor",
    "clear_active_thinking_phase",
    "coerce_thinking_call_id",
    "ensure_active_thinking_phase",
    "require_active_thinking_phase_identity",
    "resolve_active_thinking_phase_identity",
)


@dataclass(slots=True)
class ThinkingPhaseState:
    message_identity: str
    phase_index: int = 0
    last_emit_ms: int = 0
    active_sequence_index: int | None = None
    active_phase_id: str | None = None
    active_anchor_type: str | None = None
    active_anchor_call_id: str | None = None
    active_anchor_position: int | None = None
    active_start_cursor: int | None = None
    active_started_at_ms: int | None = None
    active_last_emitted_chars: int = 0
    active_committed_preface_text: str | None = None


def coerce_thinking_call_id(value: JSONValue) -> str:
    if isinstance(value, str):
        return value.strip()
    return str(value or "").strip()


def next_thinking_phase_id(thinking_state: ThinkingPhaseState) -> str:
    phase_id = f"{thinking_state.message_identity}:{thinking_state.phase_index}"
    thinking_state.phase_index += 1
    return phase_id


def ensure_active_thinking_phase(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    thinking_text: str,
    end_cursor: int,
) -> tuple[str, int, str, str | None, int | None, int] | None:
    if thinking_state.active_sequence_index is not None:
        if thinking_state.active_phase_id is None:
            raise ValidationError("Thinking phase state is invalid (missing phase id).")
        if thinking_state.active_anchor_type is None:
            raise ValidationError("Thinking phase state is invalid (missing anchor type).")
        if thinking_state.active_start_cursor is None:
            raise ValidationError("Thinking phase state is invalid (missing start cursor).")
        if thinking_state.active_started_at_ms is None:
            raise ValidationError("Thinking phase state is invalid (missing started_at_ms).")
        return (
            thinking_state.active_phase_id,
            thinking_state.active_sequence_index,
            thinking_state.active_anchor_type,
            thinking_state.active_anchor_call_id,
            thinking_state.active_anchor_position,
            thinking_state.active_started_at_ms,
        )
    start_cursor = max(0, runtime.thinking_phase_cursor)
    if end_cursor <= start_cursor:
        return None
    if not normalize_thinking_phase_text_for_rendering(
        thinking_text[start_cursor:end_cursor],
    ).strip():
        return None
    anchor = resolve_new_thinking_phase_anchor(
        runtime=runtime,
        stream_transcript=stream_transcript,
    )
    phase_id = next_thinking_phase_id(thinking_state)
    sequence_index = len(thinking_phases)
    thinking_state.active_sequence_index = sequence_index
    thinking_state.active_phase_id = phase_id
    thinking_state.active_anchor_type = anchor.anchor_type
    thinking_state.active_anchor_call_id = anchor.anchor_call_id
    thinking_state.active_anchor_position = anchor.anchor_position
    thinking_state.active_start_cursor = start_cursor
    thinking_state.active_started_at_ms = epoch_ms()
    thinking_state.active_last_emitted_chars = 0
    thinking_state.active_committed_preface_text = None
    return (
        phase_id,
        sequence_index,
        anchor.anchor_type,
        anchor.anchor_call_id,
        anchor.anchor_position,
        thinking_state.active_started_at_ms,
    )


def resolve_active_thinking_phase_identity(
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    thinking_text: str,
    end_cursor: int,
    operation: str,
) -> tuple[str, int, str, str | None, int | None, int] | None:
    if end_cursor < 0:
        raise ValidationError(f"{operation} requires end_cursor >= 0.")
    if end_cursor > len(thinking_text):
        raise ValidationError(f"{operation} requires end_cursor within thinking text bounds.")
    return ensure_active_thinking_phase(
        runtime=runtime,
        stream_transcript=stream_transcript,
        thinking_phases=thinking_phases,
        thinking_state=thinking_state,
        thinking_text=thinking_text,
        end_cursor=end_cursor,
    )


def require_active_thinking_phase_identity(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    thinking_text: str,
    end_cursor: int,
    operation: str,
    error_message: str,
) -> tuple[str, int, str, str | None, int | None, int]:
    active = resolve_active_thinking_phase_identity(
        runtime,
        stream_transcript,
        thinking_phases,
        thinking_state,
        thinking_text,
        end_cursor,
        operation,
    )
    if active is None:
        raise ValidationError(error_message)
    return active


def clear_active_thinking_phase(thinking_state: ThinkingPhaseState) -> None:
    thinking_state.active_sequence_index = None
    thinking_state.active_phase_id = None
    thinking_state.active_anchor_type = None
    thinking_state.active_anchor_call_id = None
    thinking_state.active_anchor_position = None
    thinking_state.active_start_cursor = None
    thinking_state.active_started_at_ms = None
    thinking_state.active_last_emitted_chars = 0
    thinking_state.active_committed_preface_text = None


async def advance_thinking_phase_cursor(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
    thinking_state: ThinkingPhaseState,
    boundary: int,
    on_visible_active_phase: (
        Callable[[tuple[str, int, str, str | None, int | None, int], str], Awaitable[None] | None]
        | None
    ) = None,
    allow_existing_visible_phase: bool = False,
) -> None:
    thinking_text = stream_transcript.get_thinking_text()
    if boundary < 0:
        raise ValidationError("Thinking phase cursor boundary must be non-negative.")
    if boundary > len(thinking_text):
        raise ValidationError("Thinking phase cursor boundary exceeds transcript length.")
    normalized_boundary = min(len(thinking_text), max(0, runtime.thinking_phase_cursor, boundary))
    active_sequence_index = thinking_state.active_sequence_index
    if active_sequence_index is None:
        runtime.thinking_phase_cursor = normalized_boundary
        return
    active_phase_id = thinking_state.active_phase_id
    active_anchor_type = thinking_state.active_anchor_type
    active_start_cursor = thinking_state.active_start_cursor
    active_started_at_ms = thinking_state.active_started_at_ms
    if active_phase_id is None:
        raise ValidationError("Thinking phase state is invalid (missing phase id).")
    if active_anchor_type is None:
        raise ValidationError("Thinking phase state is invalid (missing anchor type).")
    if active_start_cursor is None:
        raise ValidationError("Thinking phase state is invalid (missing start cursor).")
    if active_started_at_ms is None:
        raise ValidationError("Thinking phase state is invalid (missing started_at_ms).")
    if normalized_boundary > active_start_cursor:
        phase_text_for_emit = normalize_thinking_phase_text_for_rendering(
            thinking_text[active_start_cursor:normalized_boundary],
        )
        if phase_text_for_emit.strip():
            if on_visible_active_phase is None and not allow_existing_visible_phase:
                raise ValidationError(
                    "Thinking phase cursor advance requires visible active phase reconciliation.",
                )
            if on_visible_active_phase is not None:
                maybe_awaitable = on_visible_active_phase(
                    (
                        active_phase_id,
                        active_sequence_index,
                        active_anchor_type,
                        thinking_state.active_anchor_call_id,
                        thinking_state.active_anchor_position,
                        active_started_at_ms,
                    ),
                    phase_text_for_emit,
                )
                if maybe_awaitable is not None:
                    await maybe_awaitable
        clear_active_thinking_phase(thinking_state)
    runtime.thinking_phase_cursor = normalized_boundary
