"""SoAI - Assistant timeline runtime matching helpers [backend/features/assistant_timeline/runtime_matching.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = ("matches_assistant_timeline_runtime",)


def matches_assistant_timeline_runtime(
    *,
    runtime: AssistantTimelineRuntime,
    event_user_id: int,
    event_conv_id: str,
    event_message_index: int,
    event_turn_id: str | None,
) -> bool:
    if event_user_id != runtime.user_id or event_conv_id != runtime.conv_id:
        return False
    if event_message_index != runtime.message_index:
        return False
    runtime_turn_id = (
        runtime.agent_turn_id.strip()
        if runtime.agent_turn_id is not None and runtime.agent_turn_id.strip()
        else None
    )
    normalized_event_turn_id = (
        event_turn_id.strip() if event_turn_id and event_turn_id.strip() else None
    )
    if runtime_turn_id is not None:
        return normalized_event_turn_id == runtime_turn_id
    return normalized_event_turn_id is None
