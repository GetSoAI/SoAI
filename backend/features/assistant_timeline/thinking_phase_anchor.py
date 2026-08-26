"""SoAI - Shared assistant timeline thinking phase anchoring [backend/features/assistant_timeline/thinking_phase_anchor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "ThinkingPhaseAnchor",
    "resolve_new_thinking_phase_anchor",
    "resolve_tool_boundary_thinking_phase_anchor",
    "resolve_visible_safe_thinking_position",
)


@dataclass(frozen=True, slots=True)
class ThinkingPhaseAnchor:
    anchor_type: Literal["before_call", "after_call", "position"]
    anchor_call_id: str | None
    anchor_position: int | None


def resolve_visible_safe_thinking_position(
    runtime: AssistantTimelineRuntime,
    raw_position: int | None,
) -> int:
    resolved_position = max(0, raw_position if raw_position is not None else 0)
    if runtime.assistant_visible_chars <= 0:
        return resolved_position
    return max(resolved_position, runtime.assistant_visible_chars)


def _resolve_last_emitted_tool_call_id(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
) -> str | None:
    tool_calls = stream_transcript.get_tool_calls()
    if not tool_calls:
        return None
    last_call_id_value = tool_calls[-1].get("id")
    last_call_id = last_call_id_value.strip() if isinstance(last_call_id_value, str) else ""
    if last_call_id and last_call_id in runtime.emitted_tool_call_ids:
        return last_call_id
    return None


def _build_position_anchor(
    runtime: AssistantTimelineRuntime,
    raw_position: int | None,
) -> ThinkingPhaseAnchor:
    return ThinkingPhaseAnchor(
        anchor_type="position",
        anchor_call_id=None,
        anchor_position=resolve_visible_safe_thinking_position(runtime, raw_position),
    )


def resolve_new_thinking_phase_anchor(
    *,
    runtime: AssistantTimelineRuntime,
    stream_transcript: OpenAIStreamTranscript,
) -> ThinkingPhaseAnchor:
    raw_position = stream_transcript.get_thinking_tail_content_index_before()
    if runtime.assistant_visible_chars > 0:
        return _build_position_anchor(runtime, raw_position)
    last_call_id = _resolve_last_emitted_tool_call_id(
        runtime=runtime,
        stream_transcript=stream_transcript,
    )
    if last_call_id is not None:
        return ThinkingPhaseAnchor(
            anchor_type="after_call",
            anchor_call_id=last_call_id,
            anchor_position=None,
        )
    return _build_position_anchor(runtime, raw_position)


def resolve_tool_boundary_thinking_phase_anchor(
    *,
    runtime: AssistantTimelineRuntime,
    call_id: str,
    content_index_before: int,
    prefer_before_call: bool,
) -> ThinkingPhaseAnchor:
    if runtime.assistant_visible_chars > 0:
        return _build_position_anchor(runtime, content_index_before)
    if prefer_before_call and call_id:
        return ThinkingPhaseAnchor(
            anchor_type="before_call",
            anchor_call_id=call_id,
            anchor_position=None,
        )
    return _build_position_anchor(runtime, content_index_before)
