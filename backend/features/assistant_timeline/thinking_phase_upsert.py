"""SoAI - Shared assistant timeline thinking phase upsert primitive [backend/features/assistant_timeline/thinking_phase_upsert.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.protocols_database_message_streaming import (
    DatabaseStreamingMessagesProtocol,
)
from core.errors.exceptions import ValidationError
from core.timing.epoch import epoch_ms
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.thinking_phase import build_thinking_phase
from features.assistant_timeline.visible_activity_event_emission import (
    flush_assistant_text_then_publish_visible_event_locked,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict
    from features.assistant_timeline.thinking_phase_state import ThinkingPhaseState

__all__ = (
    "upsert_thinking_phase",
    "upsert_thinking_phase_from_identity",
)


async def upsert_thinking_phase(
    *,
    runtime: AssistantTimelineRuntime,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
    phase_id: str,
    sequence_index: int,
    anchor_type: str,
    anchor_call_id: str | None,
    anchor_position: int | None,
    phase_text: str,
    status: str,
    started_at_ms: int | None = None,
    duration_ms: int | None = None,
) -> bool:
    _require_active_thinking_phase_state(
        thinking_state=thinking_state,
        phase_id=phase_id,
        sequence_index=sequence_index,
        anchor_type=anchor_type,
        anchor_call_id=anchor_call_id,
        anchor_position=anchor_position,
        started_at_ms=started_at_ms,
    )
    _require_valid_sequence_index(
        thinking_phases=thinking_phases,
        sequence_index=sequence_index,
    )
    resolved_duration_ms = _resolve_visible_phase_duration_ms(
        status=status,
        started_at_ms=started_at_ms,
        duration_ms=duration_ms,
    )
    phase_payload = build_thinking_phase(
        phase_id=phase_id,
        sequence_index=sequence_index,
        anchor_type=anchor_type,
        anchor_call_id=anchor_call_id,
        anchor_position=anchor_position,
        phase_text=phase_text,
        duration_ms=resolved_duration_ms,
        started_at_ms=started_at_ms,
        status=status,
        committed_preface_text=thinking_state.active_committed_preface_text,
    )
    if phase_payload is None:
        return False
    _require_phase_preface_matches_state(
        thinking_state=thinking_state,
        phase_payload=phase_payload,
    )
    if sequence_index == len(thinking_phases):
        thinking_phases.append(phase_payload)
    else:
        existing = thinking_phases[sequence_index]
        if existing.get("phase_id") != phase_id:
            raise ValidationError("Thinking phase upsert phase_id mismatch.")
        if (
            existing.get("anchor_type") != anchor_type
            or existing.get("anchor_call_id") != anchor_call_id
            or existing.get("anchor_position") != anchor_position
        ):
            raise ValidationError("Thinking phase upsert anchor metadata mismatch.")
        thinking_phases[sequence_index] = phase_payload
    _commit_phase_preface(thinking_state=thinking_state, phase_payload=phase_payload)
    await flush_assistant_text_then_publish_visible_event_locked(
        event_bus=event_bus,
        runtime=runtime,
        database_messages=database_messages,
        event_type="thinking_phase",
        payload={
            "assistant_at_ms": runtime.assistant_at_ms,
            "thinking_phase": phase_payload,
        },
    )
    return True


async def upsert_thinking_phase_from_identity(
    *,
    runtime: AssistantTimelineRuntime,
    thinking_phases: list[JSONDict],
    thinking_state: ThinkingPhaseState,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
    phase_identity: tuple[str, int, str, str | None, int | None, int],
    phase_text: str,
    status: str,
    duration_ms: int | None = None,
) -> bool:
    phase_id, sequence_index, anchor_type, anchor_call_id, anchor_position, started_at_ms = (
        phase_identity
    )
    return await upsert_thinking_phase(
        runtime=runtime,
        thinking_phases=thinking_phases,
        thinking_state=thinking_state,
        database_messages=database_messages,
        event_bus=event_bus,
        phase_id=phase_id,
        sequence_index=sequence_index,
        anchor_type=anchor_type,
        anchor_call_id=anchor_call_id,
        anchor_position=anchor_position,
        phase_text=phase_text,
        started_at_ms=started_at_ms,
        status=status,
        duration_ms=duration_ms,
    )


def _require_active_thinking_phase_state(
    *,
    thinking_state: ThinkingPhaseState,
    phase_id: str,
    sequence_index: int,
    anchor_type: str,
    anchor_call_id: str | None,
    anchor_position: int | None,
    started_at_ms: int | None,
) -> None:
    if thinking_state.active_phase_id != phase_id:
        raise ValidationError("Thinking phase upsert active phase_id mismatch.")
    if thinking_state.active_sequence_index != sequence_index:
        raise ValidationError("Thinking phase upsert active sequence mismatch.")
    if thinking_state.active_anchor_type != anchor_type:
        raise ValidationError("Thinking phase upsert active anchor_type mismatch.")
    if thinking_state.active_anchor_call_id != anchor_call_id:
        raise ValidationError("Thinking phase upsert active anchor_call_id mismatch.")
    if thinking_state.active_anchor_position != anchor_position:
        raise ValidationError("Thinking phase upsert active anchor_position mismatch.")
    if thinking_state.active_start_cursor is None:
        raise ValidationError("Thinking phase upsert active start cursor is missing.")
    if thinking_state.active_started_at_ms is None:
        raise ValidationError("Thinking phase upsert active started_at_ms is missing.")
    if thinking_state.active_started_at_ms != started_at_ms:
        raise ValidationError("Thinking phase upsert active started_at_ms mismatch.")


def _require_valid_sequence_index(
    *,
    thinking_phases: list[JSONDict],
    sequence_index: int,
) -> None:
    if sequence_index == len(thinking_phases):
        return
    if 0 <= sequence_index < len(thinking_phases):
        return
    raise ValidationError("Thinking phase upsert sequence index is invalid.")


def _resolve_visible_phase_duration_ms(
    *, status: str, started_at_ms: int | None, duration_ms: int | None
) -> int | None:
    if status == "running":
        return None
    if duration_ms is not None:
        return max(0, int(duration_ms))
    if started_at_ms is None:
        raise ValidationError("Terminal thinking phase started_at_ms is missing.")
    return max(0, int(epoch_ms()) - int(started_at_ms))


def _resolve_payload_preface_text(phase_payload: JSONDict) -> str | None:
    preface_text = phase_payload.get("preface_text")
    if preface_text is None:
        return None
    if not isinstance(preface_text, str):
        raise ValidationError("Thinking phase preface_text must be a string.")
    normalized_preface_text = preface_text.strip()
    return normalized_preface_text or None


def _require_phase_preface_matches_state(
    *,
    thinking_state: ThinkingPhaseState,
    phase_payload: JSONDict,
) -> None:
    state_preface_text = thinking_state.active_committed_preface_text
    if state_preface_text is None:
        return
    payload_preface_text = _resolve_payload_preface_text(phase_payload)
    if payload_preface_text is None:
        raise ValidationError("Thinking phase committed preface mismatch.")
    if payload_preface_text == state_preface_text:
        return
    raise ValidationError("Thinking phase committed preface mismatch.")


def _commit_phase_preface(
    *,
    thinking_state: ThinkingPhaseState,
    phase_payload: JSONDict,
) -> None:
    if phase_payload.get("preface_complete") is not True:
        return
    preface_text = _resolve_payload_preface_text(phase_payload)
    if preface_text is not None:
        thinking_state.active_committed_preface_text = preface_text
