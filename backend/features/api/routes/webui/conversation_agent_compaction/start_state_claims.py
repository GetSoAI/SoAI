"""SoAI - Manual compaction start-state claiming helpers [backend/features/api/routes/webui/conversation_agent_compaction/start_state_claims.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from starlette.requests import Request

from core.agent.status_values import AGENT_TURN_STATUS_RUNNING
from core.agent.todo_state_models import AgentTurnTodoState
from core.agent.turn_record_fields import TurnStateHeader
from core.agent.turn_scope_values import TURN_SCOPE_ROOT
from core.agent.turn_state_requests import build_turn_state_request
from core.database.requests import ClaimAgentTurnStateRequest
from core.errors.exceptions import ValidationError
from core.runtime.soai_identifiers import create_prefixed_hex_id, create_system_id
from core.tool_calls.context_compaction_markers import (
    build_manual_context_compaction_call_id,
)
from core.validation.integers import is_strict_int
from features.agent.runtime.turn_engine import create_turn_execution_token
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import raise_invalid_request

__all__ = (
    "ManualCompactionStartState",
    "build_manual_compaction_start_state",
    "build_manual_compaction_turn_identity",
    "finalize_manual_compaction_start_state",
    "resolve_manual_compaction_start_message_index",
)


@dataclass(frozen=True, slots=True)
class ManualCompactionStartState:
    conv_id: str
    model: str
    mode: str
    compaction_limit: int | None
    context_window_tokens: int
    turn_id: str
    execution_token: str
    message_index: int
    iteration_index: int
    turn_cancellation_id: str
    tool_call_id: str
    started_at_ms: int
    replace_assistant_at_ms: int | None
    replace_tool_call_id: str | None
    turn_claim: ClaimAgentTurnStateRequest
    manual_regeneration_request_json: str | None = None
    manual_regeneration_expected_revision: int | None = None


def build_manual_compaction_turn_identity() -> tuple[str, str]:
    turn_id = create_prefixed_hex_id("compact", length=16)
    return (
        turn_id,
        create_system_id(
            subsystem="webui_agent_compaction",
            owner=turn_id,
            include_random_suffix=False,
        ),
    )


def _build_manual_compaction_turn_claim(
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
    execution_token: str,
    turn_cancellation_id: str,
    model: str,
    mode: str,
    todo_state: AgentTurnTodoState,
    started_at_ms: int,
) -> ClaimAgentTurnStateRequest:
    return ClaimAgentTurnStateRequest(
        turn_state=build_turn_state_request(
            conv_id=conv_id,
            user_id=user_id,
            turn_id=turn_id,
            header=TurnStateHeader(
                turn_scope=TURN_SCOPE_ROOT,
                parent_turn_id=None,
                parent_tool_call_id=None,
                parent_iteration_index=None,
                display_name=None,
                requested_model=model,
                owner_task_id=None,
            ),
            execution_token=execution_token,
            status=AGENT_TURN_STATUS_RUNNING,
            mode=mode,
            max_iterations=1,
            iteration_index=0,
            sequence=0,
            turn_cancellation_id=turn_cancellation_id,
            active_inference_cancellation_id=None,
            assistant_text=None,
            tool_calls=[],
            tool_results=[],
            activities=[],
            reached_max_iterations=False,
            error_message=None,
            error_type=None,
            todo_state=todo_state,
            started_at_ms=started_at_ms,
            updated_at_ms=started_at_ms,
            finished_at_ms=None,
        ),
    )


def build_manual_compaction_start_state(
    *,
    conv_id: str,
    user_id: int,
    model: str,
    mode: str,
    compaction_limit: int | None,
    context_window_tokens: int,
    turn_id: str,
    turn_cancellation_id: str,
    started_at_ms: int,
    message_index: int,
    todo_state: AgentTurnTodoState,
    replace_assistant_at_ms: int | None,
    replace_tool_call_id: str | None,
    manual_regeneration_request_json: str | None = None,
    manual_regeneration_expected_revision: int | None = None,
) -> ManualCompactionStartState:
    execution_token = create_turn_execution_token()
    normalized_replace_assistant_at_ms = (
        int(replace_assistant_at_ms)
        if is_strict_int(replace_assistant_at_ms) and replace_assistant_at_ms > 0
        else None
    )
    normalized_replace_tool_call_id = (
        replace_tool_call_id.strip()
        if isinstance(replace_tool_call_id, str) and replace_tool_call_id.strip()
        else None
    )
    turn_claim = _build_manual_compaction_turn_claim(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        execution_token=execution_token,
        turn_cancellation_id=turn_cancellation_id,
        model=model,
        mode=mode,
        todo_state=todo_state,
        started_at_ms=started_at_ms,
    )
    return ManualCompactionStartState(
        conv_id=conv_id,
        model=model,
        mode=mode,
        compaction_limit=compaction_limit,
        context_window_tokens=context_window_tokens,
        turn_id=turn_id,
        execution_token=execution_token,
        message_index=message_index,
        iteration_index=0,
        turn_cancellation_id=turn_cancellation_id,
        tool_call_id=build_manual_context_compaction_call_id(turn_id),
        started_at_ms=started_at_ms,
        replace_assistant_at_ms=normalized_replace_assistant_at_ms,
        replace_tool_call_id=normalized_replace_tool_call_id,
        turn_claim=turn_claim,
        manual_regeneration_request_json=manual_regeneration_request_json,
        manual_regeneration_expected_revision=manual_regeneration_expected_revision,
    )


async def finalize_manual_compaction_start_state(
    *,
    request: Request,
    user_id: int,
    conv_id: str,
    model: str,
    mode: str,
    compaction_limit: int | None,
    context_window_tokens: int | None,
    turn_id: str,
    turn_cancellation_id: str,
    started_at_ms: int,
    message_index: int,
    todo_state: AgentTurnTodoState,
    replace_assistant_at_ms: int | None,
    replace_tool_call_id: str | None,
    manual_regeneration_request_json: str | None = None,
    manual_regeneration_expected_revision: int | None = None,
) -> ManualCompactionStartState:
    if context_window_tokens is None:
        raise_invalid_request(request, "Compaction configuration is incomplete.")
    return build_manual_compaction_start_state(
        conv_id=conv_id,
        user_id=user_id,
        model=model,
        mode=mode,
        compaction_limit=compaction_limit,
        context_window_tokens=int(context_window_tokens),
        turn_id=turn_id,
        turn_cancellation_id=turn_cancellation_id,
        started_at_ms=int(started_at_ms),
        message_index=message_index,
        todo_state=todo_state,
        replace_assistant_at_ms=replace_assistant_at_ms,
        replace_tool_call_id=replace_tool_call_id,
        manual_regeneration_request_json=manual_regeneration_request_json,
        manual_regeneration_expected_revision=manual_regeneration_expected_revision,
    )


async def resolve_manual_compaction_start_message_index(
    *,
    api_context: ApiContext,
    user_id: int,
    conv_id: str,
    replace_assistant_at_ms: int | None,
) -> int:
    message_index = (
        await api_context.dependencies.database_messages.resolve_manual_compaction_message_index(
            conv_id,
            user_id,
            replace_assistant_at_ms=replace_assistant_at_ms,
        )
    )
    if message_index is None:
        raise ValidationError("Conversation messages could not be loaded.")
    return message_index
