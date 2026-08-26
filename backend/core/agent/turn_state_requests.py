"""SoAI - Agent turn-state request construction [backend/core/agent/turn_state_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.todo_state_models import AgentTurnTodoState
from core.agent.turn_record_fields import TurnStateHeader, read_turn_state_header
from core.database.requests import WriteAgentTurnStateRequest
from core.errors.exceptions import ValidationError
from core.runtime.boot_id import get_boot_id
from core.serialization.json import serialize_json_compact_stable

if TYPE_CHECKING:
    from core.runtime.protocols import RequestContextProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_turn_state_request",
    "build_turn_state_request_from_header",
    "compose_turn_state_request_from_existing_turn",
    "require_request_context_turn_execution_token",
    "require_turn_execution_token",
    "resolve_turn_execution_token",
)


def build_turn_state_request(
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
    header: TurnStateHeader,
    execution_token: str,
    expected_execution_token: str | None = None,
    status: str,
    mode: str,
    max_iterations: int,
    iteration_index: int,
    sequence: int,
    turn_cancellation_id: str | None,
    active_inference_cancellation_id: str | None,
    assistant_text: str | None,
    tool_calls: list[JSONDict],
    tool_results: list[JSONValue],
    activities: list[JSONDict],
    reached_max_iterations: bool,
    error_message: str | None,
    error_type: str | None,
    token_usage: JSONDict | None = None,
    todo_state: AgentTurnTodoState,
    started_at_ms: int,
    updated_at_ms: int,
    finished_at_ms: int | None,
) -> WriteAgentTurnStateRequest:
    return WriteAgentTurnStateRequest(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        turn_scope=header.turn_scope,
        parent_turn_id=header.parent_turn_id,
        parent_tool_call_id=header.parent_tool_call_id,
        parent_iteration_index=header.parent_iteration_index,
        display_name=header.display_name,
        requested_model=header.requested_model,
        owner_task_id=header.owner_task_id,
        execution_token=execution_token,
        server_boot_id=get_boot_id(),
        expected_execution_token=expected_execution_token,
        status=status,
        mode=mode,
        max_iterations=max_iterations,
        iteration_index=iteration_index,
        sequence=sequence,
        turn_cancellation_id=turn_cancellation_id,
        active_inference_cancellation_id=active_inference_cancellation_id,
        assistant_text=assistant_text,
        tool_calls_json=serialize_json_compact_stable(tool_calls),
        tool_results_json=serialize_json_compact_stable(tool_results),
        activities_json=serialize_json_compact_stable(activities),
        reached_max_iterations=reached_max_iterations,
        error_message=error_message,
        error_type=error_type,
        token_usage_json=(
            serialize_json_compact_stable(token_usage) if token_usage is not None else None
        ),
        todo_revision=todo_state.todo_revision,
        todo_explanation=todo_state.todo_explanation,
        todo_json=serialize_json_compact_stable(todo_state.todo),
        started_at_ms=started_at_ms,
        updated_at_ms=updated_at_ms,
        finished_at_ms=finished_at_ms,
    )


def compose_turn_state_request_from_existing_turn(
    *,
    existing_turn: JSONDict | None,
    conv_id: str,
    user_id: int,
    turn_id: str,
    execution_token: str,
    expected_execution_token: str | None = None,
    status: str,
    mode: str,
    max_iterations: int,
    iteration_index: int,
    sequence: int,
    turn_cancellation_id: str | None,
    active_inference_cancellation_id: str | None,
    assistant_text: str | None,
    tool_calls: list[JSONDict],
    tool_results: list[JSONValue],
    activities: list[JSONDict],
    reached_max_iterations: bool,
    error_message: str | None,
    error_type: str | None,
    token_usage: JSONDict | None = None,
    todo_state: AgentTurnTodoState,
    started_at_ms: int,
    updated_at_ms: int,
    finished_at_ms: int | None,
) -> WriteAgentTurnStateRequest:
    header = read_turn_state_header(existing_turn)
    return build_turn_state_request_from_header(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        header=header,
        execution_token=execution_token,
        expected_execution_token=expected_execution_token,
        status=status,
        mode=mode,
        max_iterations=max_iterations,
        iteration_index=iteration_index,
        sequence=sequence,
        turn_cancellation_id=turn_cancellation_id,
        active_inference_cancellation_id=active_inference_cancellation_id,
        assistant_text=assistant_text,
        tool_calls=tool_calls,
        tool_results=tool_results,
        activities=activities,
        reached_max_iterations=reached_max_iterations,
        error_message=error_message,
        error_type=error_type,
        token_usage=token_usage,
        todo_state=todo_state,
        started_at_ms=started_at_ms,
        updated_at_ms=updated_at_ms,
        finished_at_ms=finished_at_ms,
    )


def build_turn_state_request_from_header(
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
    header: TurnStateHeader,
    turn_scope_override: str | None = None,
    execution_token: str,
    expected_execution_token: str | None = None,
    status: str,
    mode: str,
    max_iterations: int,
    iteration_index: int,
    sequence: int,
    turn_cancellation_id: str | None,
    active_inference_cancellation_id: str | None,
    assistant_text: str | None,
    tool_calls: list[JSONDict],
    tool_results: list[JSONValue],
    activities: list[JSONDict],
    reached_max_iterations: bool,
    error_message: str | None,
    error_type: str | None,
    token_usage: JSONDict | None = None,
    todo_state: AgentTurnTodoState,
    started_at_ms: int,
    updated_at_ms: int,
    finished_at_ms: int | None,
) -> WriteAgentTurnStateRequest:
    effective_header = TurnStateHeader(
        turn_scope=turn_scope_override if turn_scope_override is not None else header.turn_scope,
        parent_turn_id=header.parent_turn_id,
        parent_tool_call_id=header.parent_tool_call_id,
        parent_iteration_index=header.parent_iteration_index,
        display_name=header.display_name,
        requested_model=header.requested_model,
        owner_task_id=header.owner_task_id,
    )
    return build_turn_state_request(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        header=effective_header,
        execution_token=execution_token,
        expected_execution_token=expected_execution_token,
        status=status,
        mode=mode,
        max_iterations=max_iterations,
        iteration_index=iteration_index,
        sequence=sequence,
        turn_cancellation_id=turn_cancellation_id,
        active_inference_cancellation_id=active_inference_cancellation_id,
        assistant_text=assistant_text,
        tool_calls=tool_calls,
        tool_results=tool_results,
        activities=activities,
        reached_max_iterations=reached_max_iterations,
        error_message=error_message,
        error_type=error_type,
        token_usage=token_usage,
        todo_state=todo_state,
        started_at_ms=started_at_ms,
        updated_at_ms=updated_at_ms,
        finished_at_ms=finished_at_ms,
    )


def resolve_turn_execution_token(turn_record: JSONDict | None) -> str | None:
    if not isinstance(turn_record, dict):
        return None
    value = turn_record.get("execution_token")
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def require_turn_execution_token(turn_record: JSONDict | None, *, operation: str) -> str:
    execution_token = resolve_turn_execution_token(turn_record)
    if execution_token is None:
        raise ValidationError(
            "Agent turn execution_token is unavailable.",
            operation=operation,
        )
    return execution_token


def require_request_context_turn_execution_token(
    context: RequestContextProtocol,
    *,
    operation: str,
) -> str:
    value = context.agent_turn_execution_token
    execution_token = value.strip() if isinstance(value, str) else ""
    if not execution_token:
        raise ValidationError(
            "Agent turn execution_token is unavailable.",
            operation=operation,
        )
    return execution_token
