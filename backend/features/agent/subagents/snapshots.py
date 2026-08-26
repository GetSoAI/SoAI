"""SoAI - Subagent snapshot normalization [backend/features/agent/subagents/snapshots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_messages import (
    resolve_agent_execution_status_message,
)
from core.agent.status_values import (
    SUBAGENT_PERSISTED_STATUSES,
    SUBAGENT_STATUS_RUNNING,
    SUBAGENT_TERMINAL_STATUSES,
)
from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.agent.turn_timing_validation import has_valid_execution_timing
from core.agent_mode import is_plan_or_execute_agent_mode
from core.execution.protocols import SubagentSnapshot
from core.serialization.json import serialize_json_compact_stable
from core.types.json_value import coerce_json_dict
from core.validation.epoch import is_unix_epoch_ms
from core.validation.integers import is_strict_int
from features.agent.subagents.result_excerpt_trimming import (
    trim_running_preview_result_excerpt,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_subagent_snapshot",
    "build_subagent_snapshots",
    "resolve_subagent_result_text",
)


def trim_subagent_result_excerpt(value: str | None) -> str | None:
    return trim_running_preview_result_excerpt(value)


def resolve_subagent_result_text(turn_record: JSONDict | None) -> str | None:
    if not isinstance(turn_record, dict):
        return None
    assistant_text = turn_record.get("assistant_text")
    if isinstance(assistant_text, str) and assistant_text.strip():
        return assistant_text.strip()
    tool_results_value = turn_record.get("tool_results")
    if not isinstance(tool_results_value, list) or not tool_results_value:
        return None
    last_result_value = tool_results_value[-1]
    last_result = coerce_json_dict(last_result_value)
    if last_result is None:
        serialized = serialize_json_compact_stable(last_result_value)
        return serialized.strip() if serialized.strip() else None
    error_value = last_result.get("error")
    if isinstance(error_value, str) and error_value.strip():
        return error_value.strip()
    result_value = last_result.get("result")
    if isinstance(result_value, str) and result_value.strip():
        return result_value.strip()
    return None


def _has_required_subagent_fields(
    *,
    owner_task_id: str | None,
    conv_id: str,
    status: str,
    mode: str,
    parent_turn_id: str,
    parent_tool_call_id: str,
) -> bool:
    if not conv_id:
        return False
    normalized_owner_task_id = str(owner_task_id or "").strip()
    if status == SUBAGENT_STATUS_RUNNING and not normalized_owner_task_id:
        return False
    if status not in SUBAGENT_PERSISTED_STATUSES:
        return False
    if not is_plan_or_execute_agent_mode(mode):
        return False
    if not parent_turn_id or not parent_tool_call_id:
        return False
    return True


def build_subagent_snapshot(turn_record: JSONDict | None) -> SubagentSnapshot | None:
    if not isinstance(turn_record, dict):
        return None
    subagent_id = str(turn_record.get("turn_id") or "").strip()
    if not subagent_id:
        return None
    if str(turn_record.get("turn_scope") or "").strip() != TURN_SCOPE_SUBAGENT:
        return None
    conv_id = str(turn_record.get("conv_id") or "").strip()
    status = str(turn_record.get("status") or "").strip()
    mode = str(turn_record.get("mode") or "").strip()
    parent_turn_id = str(turn_record.get("parent_turn_id") or "").strip()
    parent_tool_call_id = str(turn_record.get("parent_tool_call_id") or "").strip()
    parent_iteration_index = turn_record.get("parent_iteration_index")
    started_at_ms = turn_record.get("started_at_ms")
    updated_at_ms = turn_record.get("updated_at_ms")
    finished_at_ms = turn_record.get("finished_at_ms")
    owner_task_id = str(turn_record.get("owner_task_id") or "").strip() or None
    if not _has_required_subagent_fields(
        owner_task_id=owner_task_id,
        conv_id=conv_id,
        status=status,
        mode=mode,
        parent_turn_id=parent_turn_id,
        parent_tool_call_id=parent_tool_call_id,
    ):
        return None
    if not is_strict_int(parent_iteration_index):
        return None
    if not is_unix_epoch_ms(started_at_ms, enforce_maximum=False):
        return None
    if not is_unix_epoch_ms(updated_at_ms, enforce_maximum=False):
        return None
    if finished_at_ms is not None and not is_unix_epoch_ms(
        finished_at_ms,
        enforce_maximum=False,
    ):
        return None
    if not has_valid_execution_timing(
        status=status,
        running_status=SUBAGENT_STATUS_RUNNING,
        terminal_statuses=SUBAGENT_TERMINAL_STATUSES,
        started_at_ms=started_at_ms,
        updated_at_ms=updated_at_ms,
        finished_at_ms=finished_at_ms,
    ):
        return None
    token_usage = turn_record.get("token_usage")
    if token_usage is not None and not isinstance(token_usage, dict):
        return None
    error_message = str(turn_record.get("error_message") or "").strip() or None
    return SubagentSnapshot(
        execution_type=TURN_SCOPE_SUBAGENT,
        owner_task_id=owner_task_id,
        status=status,
        status_message=resolve_agent_execution_status_message(status, error_message),
        started_at_ms=started_at_ms,
        updated_at_ms=updated_at_ms,
        finished_at_ms=finished_at_ms,
        requested_model=str(turn_record.get("requested_model") or "").strip() or None,
        token_usage=token_usage,
        subagent_id=subagent_id,
        mode=mode,
        display_name=str(turn_record.get("display_name") or "").strip() or None,
        conv_id=conv_id,
        parent_turn_id=parent_turn_id,
        parent_tool_call_id=parent_tool_call_id,
        parent_iteration_index=parent_iteration_index,
        result_text=resolve_subagent_result_text(turn_record),
        error_message=error_message,
        error_type=str(turn_record.get("error_type") or "").strip() or None,
    )


def build_subagent_snapshots(turn_records: list[JSONDict]) -> list[SubagentSnapshot]:
    snapshots: list[SubagentSnapshot] = []
    for turn_record in turn_records:
        snapshot = build_subagent_snapshot(turn_record)
        if snapshot is not None:
            snapshots.append(snapshot)
    return snapshots
