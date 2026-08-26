"""SoAI - Agent bootstrap auto-compaction activity selection [backend/features/agent/runtime/turn_bootstrap_auto_compaction_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.tool_calls.context_compaction_markers import CONTEXT_COMPACTION_TOOL_NAME
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_COMPLETED,
    is_active_tool_call_status,
)
from core.types.json import JSONDict
from features.agent.runtime.turn_compaction_activity_state import (
    AUTO_COMPACTION_CALL_ID_PREFIX,
)

__all__ = ("select_initial_auto_compaction_activity",)


def select_initial_auto_compaction_activity(
    *,
    activities: list[JSONDict],
    current_turn_id: str,
) -> JSONDict | None:
    selected_completed_activity: JSONDict | None = None
    selected_completed_sequence: int | None = None
    selected_active_activity: JSONDict | None = None
    selected_active_sequence: int | None = None
    normalized_current_turn_id = current_turn_id.strip()
    for activity in activities:
        tool_name_value = activity.get("tool_name")
        tool_name = tool_name_value.strip() if isinstance(tool_name_value, str) else ""
        if tool_name != CONTEXT_COMPACTION_TOOL_NAME:
            continue
        call_id_value = activity.get("call_id")
        call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
        parsed_call_id = _parse_auto_compaction_call_id(call_id)
        if parsed_call_id is None:
            continue
        parsed_turn_id, iteration_index, created_sequence = parsed_call_id
        if parsed_turn_id != normalized_current_turn_id or iteration_index != 0:
            continue
        status_value = activity.get("status")
        status = status_value.strip() if isinstance(status_value, str) else ""
        if status == TOOL_CALL_STATUS_COMPLETED:
            if (
                selected_completed_sequence is None
                or created_sequence > selected_completed_sequence
            ):
                selected_completed_sequence = created_sequence
                selected_completed_activity = dict(activity)
            continue
        if not is_active_tool_call_status(status):
            continue
        if selected_active_sequence is None or created_sequence > selected_active_sequence:
            selected_active_sequence = created_sequence
            selected_active_activity = dict(activity)
    if selected_completed_activity is not None:
        return selected_completed_activity
    return selected_active_activity


def _parse_auto_compaction_call_id(call_id: str) -> tuple[str, int, int] | None:
    normalized_call_id = call_id.strip()
    if not normalized_call_id.startswith(AUTO_COMPACTION_CALL_ID_PREFIX):
        return None
    suffix = normalized_call_id[len(AUTO_COMPACTION_CALL_ID_PREFIX) :]
    turn_and_indexes = suffix.rsplit(":", 2)
    if len(turn_and_indexes) != 3:
        return None
    turn_id, iteration_text, created_sequence_text = turn_and_indexes
    if not turn_id.strip():
        return None
    try:
        iteration_index = int(iteration_text)
        created_sequence = int(created_sequence_text)
    except ValueError:
        return None
    if iteration_index < 0 or created_sequence < 0:
        return None
    return (turn_id, iteration_index, created_sequence)
