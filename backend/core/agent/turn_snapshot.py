"""SoAI - Agent turn snapshot normalization [backend/core/agent/turn_snapshot.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_messages import resolve_agent_execution_status_message
from core.agent.turn_record_fields import read_turn_state_header
from core.agent.turn_scope_values import TURN_SCOPE_ROOT, TURN_SCOPE_SUBAGENT
from core.agent.turn_snapshot_activity_parsers import (
    read_todo_items,
    read_tool_activities,
    read_tool_calls,
)
from core.agent.turn_snapshot_core_validation import has_valid_turn_snapshot_core
from core.agent.turn_snapshot_value_readers import (
    read_json_value_list,
    read_optional_int,
    read_optional_json_dict,
    read_optional_str,
    read_optional_text,
    read_required_bool,
    read_required_int,
    read_required_str,
)
from core.errors.exceptions import StateError
from core.execution.protocols import AgentTurnSnapshot
from core.validation.epoch import EPOCH_MS_MIN

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_agent_turn_snapshot",
    "require_agent_turn_snapshot",
)


def build_agent_turn_snapshot(turn_record: JSONDict | None) -> AgentTurnSnapshot | None:
    if not isinstance(turn_record, dict):
        return None
    conv_id = read_required_str(turn_record, "conv_id")
    if conv_id is None:
        return None
    turn_id = read_required_str(turn_record, "turn_id")
    if turn_id is None:
        return None
    turn_scope = read_required_str(turn_record, "turn_scope")
    if turn_scope is None:
        return None
    status = read_required_str(turn_record, "status")
    if status is None:
        return None
    mode = read_required_str(turn_record, "mode")
    if mode is None:
        return None
    execution_token = read_required_str(turn_record, "execution_token")
    if execution_token is None:
        return None
    server_boot_id = read_required_str(turn_record, "server_boot_id")
    if server_boot_id is None:
        return None
    user_id = read_required_int(turn_record, "user_id", minimum=1)
    if user_id is None:
        return None
    max_iterations = read_required_int(turn_record, "max_iterations", minimum=1)
    if max_iterations is None:
        return None
    iteration_index = read_required_int(turn_record, "iteration_index", minimum=0)
    if iteration_index is None:
        return None
    sequence = read_required_int(turn_record, "sequence", minimum=0)
    if sequence is None:
        return None
    todo_revision = read_required_int(turn_record, "todo_revision", minimum=0)
    if todo_revision is None:
        return None
    started_at_ms = read_required_int(turn_record, "started_at_ms", minimum=EPOCH_MS_MIN)
    if started_at_ms is None:
        return None
    updated_at_ms = read_required_int(turn_record, "updated_at_ms", minimum=EPOCH_MS_MIN)
    if updated_at_ms is None:
        return None
    finished_at_ms = read_optional_int(turn_record, "finished_at_ms", minimum=EPOCH_MS_MIN)
    reached_max_iterations = read_required_bool(turn_record, "reached_max_iterations")
    if reached_max_iterations is None:
        return None
    tool_calls = read_tool_calls(turn_record.get("tool_calls"))
    if tool_calls is None:
        return None
    tool_results = read_json_value_list(turn_record.get("tool_results"))
    if tool_results is None:
        return None
    activities = read_tool_activities(turn_record.get("activities"))
    if activities is None:
        return None
    todo = read_todo_items(turn_record.get("todo"))
    if todo is None:
        return None
    token_usage = read_optional_json_dict(turn_record, "token_usage")
    if not has_valid_turn_snapshot_core(
        conv_id=conv_id,
        turn_id=turn_id,
        turn_scope=turn_scope,
        status=status,
        mode=mode,
        execution_token=execution_token,
        server_boot_id=server_boot_id,
        user_id=user_id,
        max_iterations=max_iterations,
        iteration_index=iteration_index,
        sequence=sequence,
        todo_revision=todo_revision,
        started_at_ms=started_at_ms,
        updated_at_ms=updated_at_ms,
        finished_at_ms=finished_at_ms,
        reached_max_iterations=reached_max_iterations,
        tool_calls=tool_calls,
        tool_results=tool_results,
        activities=activities,
        todo=todo,
    ):
        return None
    if any(
        value is None
        for value in (
            conv_id,
            turn_id,
            turn_scope,
            status,
            mode,
            execution_token,
            server_boot_id,
            user_id,
            max_iterations,
            iteration_index,
            sequence,
            todo_revision,
            started_at_ms,
            updated_at_ms,
            reached_max_iterations,
            tool_calls,
            tool_results,
            activities,
            todo,
        )
    ):
        raise StateError(
            "Agent turn snapshot core validation failed unexpectedly.",
        )
    header = read_turn_state_header(turn_record)
    if header.turn_scope != turn_scope:
        return None
    parent_iteration_index = header.parent_iteration_index
    if parent_iteration_index is not None and parent_iteration_index < 0:
        return None
    parent_turn_id = header.parent_turn_id
    parent_tool_call_id = header.parent_tool_call_id
    owner_task_id = header.owner_task_id
    if turn_scope == TURN_SCOPE_ROOT:
        if (
            parent_iteration_index is not None
            or parent_turn_id is not None
            or parent_tool_call_id is not None
        ):
            return None
    if turn_scope == TURN_SCOPE_SUBAGENT:
        if (
            parent_iteration_index is None
            or parent_turn_id is None
            or parent_tool_call_id is None
            or owner_task_id is None
        ):
            return None
    return AgentTurnSnapshot(
        execution_type="agent_turn",
        owner_task_id=owner_task_id,
        status=status,
        status_message=resolve_agent_execution_status_message(
            status,
            read_optional_text(turn_record, "error_message"),
        ),
        started_at_ms=started_at_ms,
        updated_at_ms=updated_at_ms,
        finished_at_ms=finished_at_ms,
        requested_model=header.requested_model,
        token_usage=token_usage,
        conv_id=str(conv_id),
        user_id=user_id,
        turn_id=turn_id,
        turn_scope=turn_scope,
        parent_turn_id=parent_turn_id,
        parent_tool_call_id=parent_tool_call_id,
        parent_iteration_index=parent_iteration_index,
        display_name=header.display_name,
        execution_token=execution_token,
        server_boot_id=server_boot_id,
        mode=mode,
        max_iterations=max_iterations,
        iteration_index=iteration_index,
        sequence=sequence,
        turn_cancellation_id=read_optional_str(turn_record, "turn_cancellation_id"),
        active_inference_cancellation_id=read_optional_str(
            turn_record,
            "active_inference_cancellation_id",
        ),
        assistant_text=read_optional_text(turn_record, "assistant_text"),
        tool_calls=tool_calls,
        tool_results=tool_results,
        activities=activities,
        reached_max_iterations=reached_max_iterations,
        error_message=read_optional_text(turn_record, "error_message"),
        error_type=read_optional_str(turn_record, "error_type"),
        todo_revision=todo_revision,
        todo_explanation=read_optional_text(turn_record, "todo_explanation"),
        todo=todo,
    )


def require_agent_turn_snapshot(turn_record: JSONDict | None) -> AgentTurnSnapshot:
    snapshot = build_agent_turn_snapshot(turn_record)
    if snapshot is None:
        raise StateError("Agent turn snapshot is invalid.")
    return snapshot
