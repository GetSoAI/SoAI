"""SoAI - Manual compaction start-state claiming helpers [backend/features/api/routes/webui/conversation_agent_compaction/start_state_claims.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from starlette.requests import Request

from core.agent.todo_state_models import AgentTurnTodoState
from core.agent.turn_state_requests import require_turn_execution_token
from core.errors.exceptions import ConflictError, ValidationError
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.runtime.request_context_cloning import clone_request_context
from core.runtime.soai_identifiers import create_prefixed_hex_id, create_system_id
from features.agent.runtime.execution_preparation import (
    build_agent_turn_engine_dependencies,
)
from features.agent.runtime.turn_lifecycle.claim_state import (
    claim_turn_state_for_known_turn,
)
from features.api.routes.webui.conversation_agent_compaction.context import (
    build_manual_tool_call_id,
)
from features.api.runtime.context import ApiContext
from features.api.runtime.errors import (
    raise_conflict,
    raise_invalid_request,
    raise_server_error,
)

__all__ = (
    "ManualCompactionStartState",
    "build_manual_compaction_start_state",
    "build_manual_compaction_turn_identity",
    "claim_and_build_manual_compaction_start_state",
    "claim_manual_compaction_turn_execution_token",
    "finalize_manual_compaction_start_state",
    "resolve_manual_compaction_start_message_index",
)

LOGGER_NAME = "SoAI.features.api.start_state_claims"


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


def build_manual_compaction_start_state(
    *,
    conv_id: str,
    model: str,
    mode: str,
    compaction_limit: int | None,
    context_window_tokens: int,
    turn_id: str,
    execution_token: str,
    turn_cancellation_id: str,
    started_at_ms: int,
    message_index: int,
    replace_assistant_at_ms: int | None,
    replace_tool_call_id: str | None,
) -> ManualCompactionStartState:
    return ManualCompactionStartState(
        conv_id=str(conv_id),
        model=str(model),
        mode=str(mode),
        compaction_limit=compaction_limit,
        context_window_tokens=int(context_window_tokens),
        turn_id=str(turn_id),
        execution_token=str(execution_token),
        message_index=int(message_index),
        iteration_index=0,
        turn_cancellation_id=str(turn_cancellation_id),
        tool_call_id=build_manual_tool_call_id(str(turn_id)),
        started_at_ms=int(started_at_ms),
        replace_assistant_at_ms=(
            int(replace_assistant_at_ms)
            if isinstance(replace_assistant_at_ms, int)
            and not isinstance(replace_assistant_at_ms, bool)
            and replace_assistant_at_ms > 0
            else None
        ),
        replace_tool_call_id=(
            replace_tool_call_id.strip()
            if isinstance(replace_tool_call_id, str) and replace_tool_call_id.strip()
            else None
        ),
    )


async def claim_manual_compaction_turn_execution_token(
    *,
    request: Request,
    api_context: ApiContext,
    user_id: int,
    conv_id: str,
    turn_id: str,
    mode: str,
    turn_cancellation_id: str,
    message_index: int,
    todo_state: AgentTurnTodoState,
    bind_owner: str,
    operation: str,
) -> str:
    try:
        claim_base_context = request.state.context
    except AttributeError:
        raise_server_error(request, "Request context is not available.")
    if not isinstance(claim_base_context, RequestContext):
        raise_server_error(request, "Request context is invalid.")
    claim_context = clone_request_context(claim_base_context)
    if not isinstance(claim_context, RequestContext):
        raise_server_error(request, "Request context clone is invalid.")
    claimed_turn = await claim_turn_state_for_known_turn(
        deps=build_agent_turn_engine_dependencies(
            api_dependencies=api_context.dependencies,
            logger=get_logger(LOGGER_NAME),
        ),
        context=claim_context,
        conv_id=conv_id,
        message_index=message_index,
        user_id=user_id,
        turn_id=turn_id,
        mode=mode,
        max_iterations=1,
        turn_cancellation_id=turn_cancellation_id,
        todo_state=todo_state,
        initial_active_inference_cancellation_id=None,
        bind_owner=bind_owner,
    )
    turn_record = claimed_turn.turn_record
    return require_turn_execution_token(turn_record, operation=operation)


async def claim_and_build_manual_compaction_start_state(
    *,
    request: Request,
    api_context: ApiContext,
    user_id: int,
    conv_id: str,
    model: str,
    mode: str,
    compaction_limit: int | None,
    context_window_tokens: int,
    turn_id: str,
    turn_cancellation_id: str,
    started_at_ms: int,
    message_index: int,
    todo_state: AgentTurnTodoState,
    bind_owner: str,
    operation: str,
    replace_assistant_at_ms: int | None,
    replace_tool_call_id: str | None,
) -> ManualCompactionStartState:
    try:
        execution_token = await claim_manual_compaction_turn_execution_token(
            request=request,
            api_context=api_context,
            user_id=user_id,
            conv_id=conv_id,
            turn_id=turn_id,
            mode=mode,
            turn_cancellation_id=turn_cancellation_id,
            message_index=message_index,
            todo_state=todo_state,
            bind_owner=bind_owner,
            operation=operation,
        )
    except ConflictError:
        raise_conflict(request, "Compaction unavailable while agent is running.")
    return build_manual_compaction_start_state(
        conv_id=conv_id,
        model=model,
        mode=mode,
        compaction_limit=compaction_limit,
        context_window_tokens=context_window_tokens,
        turn_id=turn_id,
        execution_token=execution_token,
        turn_cancellation_id=turn_cancellation_id,
        started_at_ms=int(started_at_ms),
        message_index=message_index,
        replace_assistant_at_ms=replace_assistant_at_ms,
        replace_tool_call_id=replace_tool_call_id,
    )


async def finalize_manual_compaction_start_state(
    *,
    request: Request,
    api_context: ApiContext,
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
    bind_owner: str,
    operation: str,
    replace_assistant_at_ms: int | None,
    replace_tool_call_id: str | None,
) -> ManualCompactionStartState:
    if context_window_tokens is None:
        raise_invalid_request(request, "Compaction configuration is incomplete.")
    return await claim_and_build_manual_compaction_start_state(
        request=request,
        api_context=api_context,
        user_id=user_id,
        conv_id=conv_id,
        model=model,
        mode=mode,
        compaction_limit=compaction_limit,
        context_window_tokens=int(context_window_tokens),
        turn_id=turn_id,
        turn_cancellation_id=turn_cancellation_id,
        started_at_ms=int(started_at_ms),
        message_index=message_index,
        todo_state=todo_state,
        bind_owner=bind_owner,
        operation=operation,
        replace_assistant_at_ms=replace_assistant_at_ms,
        replace_tool_call_id=replace_tool_call_id,
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
