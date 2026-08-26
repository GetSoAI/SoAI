"""SoAI - Tool activity snapshot merging helpers [backend/core/tool_calls/activity_snapshot_merging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.tool_calls.tool_event_payloads import map_tool_call_event_to_tool_payload
from core.types.json import JSONDict
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict

if TYPE_CHECKING:
    from core.events.types_conversation import (
        ToolCallCompletedEvent,
        ToolCallCreatedEvent,
        ToolCallStartedEvent,
    )

__all__ = ("upsert_tool_activity_snapshot",)


def upsert_tool_activity_snapshot(
    activities: list[JSONDict],
    *,
    event: ToolCallCreatedEvent | ToolCallStartedEvent | ToolCallCompletedEvent,
    activity_sequence: int,
    text_length_before: int,
) -> list[JSONDict]:
    normalized_payload = map_tool_call_event_to_tool_payload(event)
    call_id = str(normalized_payload.get("call_id") or "").strip()
    if not call_id:
        raise ValidationError("Tool activity call_id is required.")
    normalized_activity_sequence = max(0, int(activity_sequence))
    normalized_text_length_before = max(0, int(text_length_before))
    merged_activities = [dict(activity) for activity in activities]
    for index, activity in enumerate(merged_activities):
        existing_call_id = str(activity.get("call_id") or "").strip()
        if existing_call_id != call_id:
            continue
        merged_activity = dict(activity)
        merged_activity.update(normalized_payload)
        started_sequence = activity.get("started_sequence")
        text_length_value = activity.get("text_length_before")
        merged_activity["started_sequence"] = (
            int(started_sequence)
            if isinstance(started_sequence, int) and started_sequence >= 0
            else normalized_activity_sequence
        )
        merged_activity["text_length_before"] = (
            int(text_length_value)
            if isinstance(text_length_value, int) and text_length_value >= 0
            else normalized_text_length_before
        )
        merged_activity["last_sequence"] = max(
            normalized_activity_sequence,
            coerce_optional_non_negative_int_strict(activity.get("last_sequence")) or 0,
        )
        merged_activities[index] = merged_activity
        return merged_activities
    normalized_payload["started_sequence"] = normalized_activity_sequence
    normalized_payload["last_sequence"] = normalized_activity_sequence
    normalized_payload["text_length_before"] = normalized_text_length_before
    merged_activities.append(normalized_payload)
    return merged_activities
