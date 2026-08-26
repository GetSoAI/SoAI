"""SoAI - Assistant timeline loading activity payloads [backend/features/assistant_timeline/loading_activity_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.activity_payloads import build_activity_payload
from core.timing.monotonic import monotonic_ms

if TYPE_CHECKING:
    from core.conversations.protocols_database_conversations import (
        DatabaseMessagesProtocol,
    )
    from core.types.json import JSONDict
    from features.assistant_timeline.models import AssistantTimelineRuntime

__all__ = (
    "build_loading_activity_event_payload",
    "build_loading_activity_payload",
    "sync_runtime_event_sequence_with_database",
)


def build_loading_activity_payload(
    *,
    runtime: AssistantTimelineRuntime,
    status: str,
    duration_ms: int,
    reason: str | None = None,
    error_type: str | None = None,
) -> JSONDict:
    started_at_epoch_ms = runtime.loading_activity.started_at_epoch_ms
    if started_at_epoch_ms is None or started_at_epoch_ms < 0:
        fallback = max(0, int(runtime.assistant_at_ms))
        runtime.loading_activity.started_at_epoch_ms = fallback
        started_at_epoch_ms = fallback
    return build_activity_payload(
        status=status,
        started_at_ms=started_at_epoch_ms,
        duration_ms=duration_ms,
        reason=reason,
        error_type=error_type,
    )


def build_loading_activity_event_payload(
    *,
    runtime: AssistantTimelineRuntime,
    loading_activity: JSONDict,
) -> JSONDict:
    return {
        "assistant_at_ms": runtime.assistant_at_ms,
        "loading_activity": loading_activity,
    }


async def sync_runtime_event_sequence_with_database(
    *,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseMessagesProtocol,
) -> None:
    if runtime.next_sequence != 0 or runtime.assistant_revision != 0:
        return
    if runtime.assistant_event_buffer:
        return
    message_state = await database_messages.get_assistant_turn_variant_stream_state(
        runtime.conv_id,
        runtime.user_id,
        runtime.assistant_turn_at_ms,
        runtime.model_variant_index,
    )
    if not isinstance(message_state, dict):
        return
    timeline_value = message_state.get("assistant_event_timeline")
    if not isinstance(timeline_value, list):
        return
    max_sequence = -1
    for entry in timeline_value:
        if not isinstance(entry, dict):
            continue
        sequence_value = entry.get("sequence")
        if (
            isinstance(sequence_value, bool)
            or not isinstance(sequence_value, int)
            or sequence_value < 0
        ):
            continue
        max_sequence = max(max_sequence, sequence_value)
    next_sequence = max_sequence + 1
    if next_sequence <= 0:
        return
    runtime.next_sequence = next_sequence
    runtime.assistant_revision = next_sequence
    now_ms = monotonic_ms()
    runtime.last_visible_activity_monotonic_ms = max(
        runtime.last_visible_activity_monotonic_ms,
        now_ms,
    )
