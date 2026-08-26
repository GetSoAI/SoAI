"""SoAI - Compaction marker extraction [backend/database/repositories/users/message_compaction_markers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.pinned_prefix import split_leading_pinned_prefix
from core.tool_calls.context_compaction_boundary_resolution import (
    resolve_context_compaction_boundaries_from_markers,
)
from core.tool_calls.context_compaction_markers import (
    extract_context_compaction_markers_from_assistant_timeline,
    is_context_compaction_active_completed_marker,
)
from core.tool_calls.context_compaction_metrics import (
    resolve_context_compaction_tokens_saved_from_details,
)
from core.tool_calls.status_values import TOOL_CALL_STATUS_COMPLETED

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("attach_context_compaction_markers",)


def _build_compaction_stats(markers: list[JSONDict]) -> JSONDict | None:
    if not markers:
        return None
    completed_count = 0
    tokens_saved = 0
    for marker in markers:
        status_value = marker.get("status")
        status = status_value.strip() if isinstance(status_value, str) else ""
        if status != TOOL_CALL_STATUS_COMPLETED:
            continue
        completed_count += 1
        details_value = marker.get("details")
        details = details_value if isinstance(details_value, dict) else None
        tokens_saved += resolve_context_compaction_tokens_saved_from_details(status, details)
    if completed_count <= 0:
        return None
    return {"count": completed_count, "tokens_saved": tokens_saved}


def attach_context_compaction_markers(messages: list[JSONDict]) -> None:
    message_markers: list[JSONDict | None] = []
    for message in messages:
        marker: JSONDict | None = None
        if message.get("role") != "assistant":
            message_markers.append(marker)
            continue
        timeline_value = message.get("assistant_event_timeline")
        if not isinstance(timeline_value, list):
            message_markers.append(marker)
            continue
        markers = extract_context_compaction_markers_from_assistant_timeline(timeline_value)
        if not markers:
            message_markers.append(marker)
            continue
        marker = markers[-1]
        marker["is_active_boundary"] = False
        message["soai_compaction"] = marker
        stats = _build_compaction_stats(markers)
        if stats is not None:
            message["soai_compaction_stats"] = stats
        message_markers.append(marker)
    resolution = resolve_context_compaction_boundaries_from_markers(
        messages,
        message_markers,
        strip_leading_pinned_prefix=True,
    )
    active_message_index = resolution.active_message_index
    if active_message_index is None:
        return
    pinned_prefix, message_body = split_leading_pinned_prefix(messages)
    if active_message_index >= len(message_body):
        return
    active_original_index = len(pinned_prefix) + active_message_index
    for message_index, message in enumerate(messages):
        marker_value = message.get("soai_compaction")
        if not isinstance(marker_value, dict):
            continue
        if not is_context_compaction_active_completed_marker(marker_value):
            continue
        marker_value["is_active_boundary"] = message_index == active_original_index
