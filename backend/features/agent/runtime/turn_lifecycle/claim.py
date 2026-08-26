"""SoAI - Agent turn claim entrypoints [backend/features/agent/runtime/turn_lifecycle/claim.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.turn_state_requests import require_turn_execution_token
from core.runtime.cancellation_ids import build_agent_iteration_cancellation_id
from core.runtime.request_context import RequestContext
from core.runtime.request_context_agent_fields import apply_agent_runtime_context_fields
from features.agent.runtime.turn_engine import (
    TurnPrimitives,
    resolve_existing_turn_id,
    resolve_turn_primitives,
)
from features.agent.runtime.turn_lifecycle.claim_state import (
    ClaimedAgentTurnState,
    claim_turn_state_from_primitives,
)
from features.agent.runtime.turn_state_running_persistence import (
    persist_active_inference_cancellation_id,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.agent.todo_state_models import AgentTurnTodoState
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.agent.runtime.turn_engine import AgentTurnEngineDependencies

__all__ = (
    "claim_agent_turn_for_execution",
    "claim_agent_turn_for_streaming_execution",
)


def _prepare_agent_turn_primitives(
    *,
    context: RequestContext,
    tool_context: MCPToolContext,
    settings: AgentSettings,
    requested_model: str | None,
) -> TurnPrimitives:
    apply_agent_runtime_context_fields(
        context=context,
        settings=settings,
        requested_model=requested_model,
        turn_scope=context.agent_turn_scope,
    )
    return resolve_turn_primitives(
        context=context,
        tool_context=tool_context,
        mode=settings.mode,
        turn_id=resolve_existing_turn_id(context),
    )


async def _claim_agent_turn_from_primitives(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    settings: AgentSettings,
    todo_state: AgentTurnTodoState,
    primitives: TurnPrimitives,
    initial_active_inference_cancellation_id: str | None,
) -> ClaimedAgentTurnState:
    return await claim_turn_state_from_primitives(
        deps=deps,
        context=context,
        primitives=primitives,
        mode=settings.mode,
        max_iterations=settings.max_iterations,
        todo_state=todo_state,
        initial_active_inference_cancellation_id=initial_active_inference_cancellation_id,
        bind_owner="agent.turn.claim",
    )


async def claim_agent_turn_for_execution(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    settings: AgentSettings,
    requested_model: str | None,
    todo_state: AgentTurnTodoState,
    initial_active_inference_cancellation_id: str | None,
) -> tuple[TurnPrimitives, JSONDict]:
    primitives = _prepare_agent_turn_primitives(
        context=context,
        tool_context=tool_context,
        settings=settings,
        requested_model=requested_model,
    )
    claimed_turn = await _claim_agent_turn_from_primitives(
        deps=deps,
        context=context,
        settings=settings,
        todo_state=todo_state,
        primitives=primitives,
        initial_active_inference_cancellation_id=initial_active_inference_cancellation_id,
    )
    return (claimed_turn.primitives, claimed_turn.turn_record)


async def claim_agent_turn_for_streaming_execution(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    settings: AgentSettings,
    requested_model: str | None,
    todo_state: AgentTurnTodoState,
    initial_iteration_index: int = 0,
) -> tuple[TurnPrimitives, JSONDict, str]:
    primitives = _prepare_agent_turn_primitives(
        context=context,
        tool_context=tool_context,
        settings=settings,
        requested_model=requested_model,
    )
    initial_inference_cancellation_id = build_agent_iteration_cancellation_id(
        turn_cancellation_id=primitives.turn_cancellation_id,
        iteration_index=initial_iteration_index,
        mode=settings.mode,
    )
    claimed_turn = await _claim_agent_turn_from_primitives(
        deps=deps,
        context=context,
        settings=settings,
        todo_state=todo_state,
        primitives=primitives,
        initial_active_inference_cancellation_id=initial_inference_cancellation_id,
    )
    resolved_initial_inference_cancellation_id = build_agent_iteration_cancellation_id(
        turn_cancellation_id=claimed_turn.primitives.turn_cancellation_id,
        iteration_index=initial_iteration_index,
        mode=settings.mode,
    )
    turn_record = claimed_turn.turn_record
    if resolved_initial_inference_cancellation_id != initial_inference_cancellation_id:
        execution_token = require_turn_execution_token(
            turn_record,
            operation="agent.turn_lifecycle.claim.claim_agent_turn_for_streaming_execution",
        )
        turn_record = await persist_active_inference_cancellation_id(
            deps.database_agent_turns,
            record=turn_record,
            execution_token=execution_token,
            expected_execution_token=execution_token,
            active_inference_cancellation_id=resolved_initial_inference_cancellation_id,
            stale_running_turns=(),
        )
    return (
        claimed_turn.primitives,
        turn_record,
        resolved_initial_inference_cancellation_id,
    )
