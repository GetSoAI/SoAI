"""SoAI - Agent turn-state rewrite builders from persisted records [backend/core/agent/turn_state_record_rewrites.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_RUNNING
from core.agent.todo_state_parsing import parse_agent_todo_state_from_turn_record
from core.agent.turn_record_fields import (
    read_turn_assistant_text,
    read_turn_int,
    read_turn_optional_content_text,
    read_turn_optional_text,
    read_turn_payload_entries,
    read_turn_payload_values,
    read_turn_state_header,
    read_turn_token_usage,
)
from core.agent.turn_scope_values import TURN_SCOPE_ROOT
from core.agent.turn_state_requests import build_turn_state_request_from_header
from core.database.requests import WriteAgentTurnStateRequest
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_running_turn_state_request_from_record",
    "build_terminal_turn_state_request_from_record",
)


def _read_record_conv_id(record: JSONDict) -> str:
    return str(record.get("conv_id") or "")


def _read_record_user_id(record: JSONDict) -> int:
    return max(0, read_turn_int(record, "user_id") or 0)


def _read_record_turn_id(record: JSONDict) -> str:
    return str(record.get("turn_id") or "")


def _read_record_mode(record: JSONDict) -> str:
    return str(record.get("mode") or "")


def _read_record_max_iterations(record: JSONDict) -> int:
    return max(1, read_turn_int(record, "max_iterations") or 1)


def _read_record_iteration_index(record: JSONDict) -> int:
    return max(0, read_turn_int(record, "iteration_index") or 0)


def _read_record_sequence(record: JSONDict) -> int:
    return max(0, read_turn_int(record, "sequence") or 0)


def _read_record_started_at_ms(record: JSONDict, fallback_updated_at_ms: int) -> int:
    return max(0, read_turn_int(record, "started_at_ms") or fallback_updated_at_ms)


def build_running_turn_state_request_from_record(
    *,
    record: JSONDict,
    execution_token: str,
    expected_execution_token: str | None,
    active_inference_cancellation_id: str | None,
) -> WriteAgentTurnStateRequest:
    header = read_turn_state_header(record)
    updated_at_ms = epoch_ms()
    todo_state = parse_agent_todo_state_from_turn_record(record)
    return build_turn_state_request_from_header(
        conv_id=_read_record_conv_id(record),
        user_id=_read_record_user_id(record),
        turn_id=_read_record_turn_id(record),
        header=header,
        execution_token=execution_token,
        expected_execution_token=expected_execution_token,
        status=AGENT_TURN_STATUS_RUNNING,
        mode=_read_record_mode(record),
        max_iterations=_read_record_max_iterations(record),
        iteration_index=_read_record_iteration_index(record),
        sequence=_read_record_sequence(record),
        turn_cancellation_id=read_turn_optional_text(record, "turn_cancellation_id"),
        active_inference_cancellation_id=active_inference_cancellation_id,
        assistant_text=read_turn_assistant_text(record),
        tool_calls=read_turn_payload_entries(record, "tool_calls"),
        tool_results=read_turn_payload_values(record, "tool_results"),
        activities=read_turn_payload_entries(record, "activities"),
        reached_max_iterations=record.get("reached_max_iterations") is True,
        error_message=read_turn_optional_content_text(record, "error_message"),
        error_type=read_turn_optional_text(record, "error_type"),
        token_usage=read_turn_token_usage(record),
        todo_state=todo_state,
        started_at_ms=_read_record_started_at_ms(record, updated_at_ms),
        updated_at_ms=updated_at_ms,
        finished_at_ms=None,
    )


def build_terminal_turn_state_request_from_record(
    *,
    record: JSONDict,
    execution_token: str,
    status: str,
    iteration_index: int,
    sequence: int,
    turn_cancellation_id: str | None,
    reached_max_iterations: bool,
    error_message: str | None,
    error_type: str | None,
    active_inference_cancellation_id: str | None,
    updated_at_ms: int,
    finished_at_ms: int | None,
) -> WriteAgentTurnStateRequest:
    header = read_turn_state_header(record)
    todo_state = parse_agent_todo_state_from_turn_record(record)
    return build_turn_state_request_from_header(
        conv_id=_read_record_conv_id(record),
        user_id=_read_record_user_id(record),
        turn_id=_read_record_turn_id(record),
        header=header,
        turn_scope_override=TURN_SCOPE_ROOT if not header.turn_scope else None,
        execution_token=execution_token,
        status=status,
        mode=_read_record_mode(record),
        max_iterations=_read_record_max_iterations(record),
        iteration_index=max(0, int(iteration_index)),
        sequence=max(0, int(sequence)),
        turn_cancellation_id=turn_cancellation_id,
        active_inference_cancellation_id=active_inference_cancellation_id,
        assistant_text=read_turn_assistant_text(record),
        tool_calls=read_turn_payload_entries(record, "tool_calls"),
        tool_results=read_turn_payload_values(record, "tool_results"),
        activities=read_turn_payload_entries(record, "activities"),
        reached_max_iterations=bool(reached_max_iterations),
        error_message=error_message,
        error_type=error_type,
        token_usage=read_turn_token_usage(record),
        todo_state=todo_state,
        started_at_ms=_read_record_started_at_ms(record, updated_at_ms),
        updated_at_ms=int(updated_at_ms),
        finished_at_ms=finished_at_ms,
    )
