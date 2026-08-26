"""SoAI - Agent turn lifecycle state transitions [backend/features/agent/runtime/turn_lifecycle/transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_RUNNING
from core.agent.turn_record_fields import TurnStateHeader
from core.agent.turn_scope_values import TURN_SCOPE_ROOT
from core.agent.turn_state_requests import build_turn_state_request
from core.database.requests import ClaimAgentTurnStateRequest
from core.errors.exceptions import ConflictError, ValidationError
from core.timing.epoch import epoch_ms
from features.agent.runtime.turn_engine import create_turn_execution_token
from features.agent.runtime.turn_state_invariants import normalize_turn_start_inputs
from features.agent.runtime.turn_state_reconciliation import (
    collect_stale_running_turn_claims,
)
from features.agent.runtime.turn_state_resume import resume_existing_turn_state

if TYPE_CHECKING:
    from core.agent.todo_state_models import AgentTurnTodoState
    from core.conversations.protocols_database_agents import DatabaseAgentTurnsProtocol
    from core.tasks.protocols import TokenCollectionProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.turn_engine import AgentTurnEngineDependencies

__all__ = (
    "start_new_turn_state",
    "start_or_resume_turn_state",
)


async def start_new_turn_state(
    *,
    database_agent_turns: DatabaseAgentTurnsProtocol,
    database_tool_calls: DatabaseToolCallsProtocol,
    task_registry_queries: TaskRegistryQueryView,
    token_collection: TokenCollectionProtocol,
    conv_id: str,
    user_id: int,
    turn_id: str,
    mode: str,
    max_iterations: int,
    turn_cancellation_id: str,
    initial_active_inference_cancellation_id: str | None,
    todo_state: AgentTurnTodoState,
    header: TurnStateHeader,
) -> JSONDict:
    (
        normalized_conv_id,
        normalized_user_id,
        normalized_turn_id,
        normalized_mode,
        normalized_max_iterations,
        normalized_turn_cancellation_id,
        normalized_active_inference_cancellation_id,
    ) = normalize_turn_start_inputs(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        mode=mode,
        max_iterations=max_iterations,
        turn_cancellation_id=turn_cancellation_id,
        initial_active_inference_cancellation_id=initial_active_inference_cancellation_id,
    )
    now = epoch_ms()
    turn_state = build_turn_state_request(
        conv_id=normalized_conv_id,
        user_id=normalized_user_id,
        turn_id=normalized_turn_id,
        header=header,
        execution_token=create_turn_execution_token(),
        status=AGENT_TURN_STATUS_RUNNING,
        mode=normalized_mode,
        max_iterations=normalized_max_iterations,
        iteration_index=0,
        sequence=0,
        turn_cancellation_id=normalized_turn_cancellation_id,
        active_inference_cancellation_id=normalized_active_inference_cancellation_id,
        assistant_text=None,
        tool_calls=[],
        tool_results=[],
        activities=[],
        reached_max_iterations=False,
        error_message=None,
        error_type=None,
        todo_state=todo_state,
        started_at_ms=now,
        updated_at_ms=now,
        finished_at_ms=None,
    )
    try:
        return await database_agent_turns.claim_turn_state(
            ClaimAgentTurnStateRequest(
                turn_state=turn_state,
                stale_running_turns=await collect_stale_running_turn_claims(
                    database_agent_turns=database_agent_turns,
                    database_tool_calls=database_tool_calls,
                    task_registry_queries=task_registry_queries,
                    token_collection=token_collection,
                    conv_id=normalized_conv_id,
                    user_id=normalized_user_id,
                    turn_scope=header.turn_scope,
                    exclude_turn_id=normalized_turn_id,
                ),
            ),
        )
    except ValidationError as exception:
        raise ConflictError(str(exception) or "Agent turn already running.") from exception


async def start_or_resume_turn_state(
    deps: AgentTurnEngineDependencies,
    *,
    conv_id: str,
    user_id: int,
    turn_id: str,
    mode: str,
    max_iterations: int,
    turn_cancellation_id: str,
    initial_active_inference_cancellation_id: str | None,
    todo_state: AgentTurnTodoState,
    existing_execution_token: str | None = None,
    turn_scope: str = TURN_SCOPE_ROOT,
    parent_turn_id: str | None = None,
    parent_tool_call_id: str | None = None,
    parent_iteration_index: int | None = None,
    display_name: str | None = None,
    requested_model: str | None = None,
    owner_task_id: str | None = None,
) -> JSONDict:
    (
        normalized_conv_id,
        normalized_user_id,
        normalized_turn_id,
        normalized_mode,
        normalized_max_iterations,
        normalized_turn_cancellation_id,
        normalized_active_inference_cancellation_id,
    ) = normalize_turn_start_inputs(
        conv_id=conv_id,
        user_id=user_id,
        turn_id=turn_id,
        mode=mode,
        max_iterations=max_iterations,
        turn_cancellation_id=turn_cancellation_id,
        initial_active_inference_cancellation_id=initial_active_inference_cancellation_id,
    )
    header = TurnStateHeader(
        turn_scope=turn_scope,
        parent_turn_id=parent_turn_id,
        parent_tool_call_id=parent_tool_call_id,
        parent_iteration_index=parent_iteration_index,
        display_name=display_name,
        requested_model=requested_model,
        owner_task_id=owner_task_id,
    )
    resumed_turn = await resume_existing_turn_state(
        deps,
        conv_id=normalized_conv_id,
        user_id=normalized_user_id,
        turn_id=normalized_turn_id,
        mode=normalized_mode,
        max_iterations=normalized_max_iterations,
        active_inference_cancellation_id=normalized_active_inference_cancellation_id,
        existing_execution_token=existing_execution_token,
        header=header,
    )
    if resumed_turn is not None:
        return resumed_turn
    return await start_new_turn_state(
        database_agent_turns=deps.database_agent_turns,
        database_tool_calls=deps.database_tool_calls,
        task_registry_queries=deps.task_registry_queries,
        token_collection=deps.token_collection,
        conv_id=normalized_conv_id,
        user_id=normalized_user_id,
        turn_id=normalized_turn_id,
        mode=normalized_mode,
        max_iterations=normalized_max_iterations,
        turn_cancellation_id=normalized_turn_cancellation_id,
        initial_active_inference_cancellation_id=initial_active_inference_cancellation_id,
        todo_state=todo_state,
        header=header,
    )
