"""SoAI - Agent turn state claim primitives [backend/features/agent/runtime/turn_lifecycle/claim_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from core.agent.turn_scope_values import TURN_SCOPE_ROOT
from core.agent.turn_state_requests import require_turn_execution_token
from core.conversations.input_claim import ConversationInputClaim
from core.errors.exceptions import ConflictError, ValidationError
from core.skills.checkpoint import SkillActivationCheckpoint
from core.validation.strings import coerce_optional_trimmed_str
from features.agent.runtime.turn_engine import TurnPrimitives
from features.agent.runtime.turn_lifecycle.transitions import start_or_resume_turn_state
from features.agent.runtime.turn_todo_state import (
    build_turn_todo_state_from_turn_record,
)

if TYPE_CHECKING:
    from core.agent.todo_state_models import AgentTurnTodoState
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.agent.runtime.turn_engine import AgentTurnEngineDependencies

__all__ = (
    "ClaimedAgentTurnState",
    "claim_turn_state_for_known_turn",
    "claim_turn_state_from_primitives",
)


@dataclass(frozen=True, slots=True)
class ClaimedAgentTurnState:
    primitives: TurnPrimitives
    turn_record: JSONDict
    todo_state: AgentTurnTodoState
    skill_activation: SkillActivationCheckpoint | None
    skill_input_claim: ConversationInputClaim | None


def _reconcile_primitives_from_turn_record(
    primitives: TurnPrimitives,
    turn_record: JSONDict,
) -> TurnPrimitives:
    resolved_turn_cancellation_id = coerce_optional_trimmed_str(
        turn_record.get("turn_cancellation_id"),
    )
    if (
        resolved_turn_cancellation_id is None
        or resolved_turn_cancellation_id == primitives.turn_cancellation_id
    ):
        return primitives
    return TurnPrimitives(
        start_time=primitives.start_time,
        base_cancellation_id=primitives.base_cancellation_id,
        conv_id=primitives.conv_id,
        message_index=primitives.message_index,
        user_id=primitives.user_id,
        turn_id=primitives.turn_id,
        turn_cancellation_id=resolved_turn_cancellation_id,
    )


async def claim_turn_state_from_primitives(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    primitives: TurnPrimitives,
    mode: str,
    max_iterations: int,
    todo_state: AgentTurnTodoState,
    initial_active_inference_cancellation_id: str | None,
    bind_owner: str,
) -> ClaimedAgentTurnState:
    replay_snapshot = context.agent_prompt_replay_snapshot
    claimed_execution_token = (
        replay_snapshot.claimed_execution_token if replay_snapshot is not None else None
    )
    if (
        claimed_execution_token is not None
        and claimed_execution_token != context.agent_turn_execution_token
    ):
        raise ConflictError("Agent replay claim token changed before bootstrap.")
    admission_snapshot = replay_snapshot if claimed_execution_token is None else None
    skill_activation = None
    skill_input_claim = None
    if (
        context.skill_execution_context is not None
        and context.skill_execution_context.snapshot.available
    ):
        skill_activation = SkillActivationCheckpoint.from_execution(context.skill_execution_context)
        skill_input_claim = ConversationInputClaim.from_fields(
            context.conversation_input_id,
            context.conversation_input_claim_generation,
            context.conversation_input_claim_owner,
            context.conversation_input_server_boot_id,
        )
    turn_record = await start_or_resume_turn_state(
        deps,
        conv_id=primitives.conv_id,
        user_id=primitives.user_id,
        turn_id=primitives.turn_id,
        mode=mode,
        max_iterations=max_iterations,
        turn_cancellation_id=primitives.turn_cancellation_id,
        initial_active_inference_cancellation_id=initial_active_inference_cancellation_id,
        todo_state=todo_state,
        existing_execution_token=context.agent_turn_execution_token,
        prompt_replay_snapshot=admission_snapshot,
        turn_scope=context.agent_turn_scope or TURN_SCOPE_ROOT,
        parent_turn_id=context.agent_parent_turn_id,
        parent_tool_call_id=context.agent_parent_tool_call_id,
        parent_iteration_index=context.agent_parent_iteration_index,
        display_name=context.agent_display_name,
        requested_model=context.agent_requested_model,
        owner_task_id=context.agent_owner_task_id,
        skill_activation=skill_activation,
        skill_input_claim=skill_input_claim,
    )
    context.agent_turn_execution_token = require_turn_execution_token(
        turn_record,
        operation="agent.turn_lifecycle.claim_state.claim_turn_state_from_primitives",
    )
    if admission_snapshot is not None:
        context.agent_prompt_replay_snapshot = replace(
            admission_snapshot, claimed_execution_token=context.agent_turn_execution_token
        )
    resolved_primitives = _reconcile_primitives_from_turn_record(primitives, turn_record)
    context.agent_turn_id = resolved_primitives.turn_id
    if context.agent_turn_scope is None:
        context.agent_turn_scope = TURN_SCOPE_ROOT
    current_task = asyncio.current_task()
    if current_task is None:
        raise ValidationError("Agent turn claim requires a running asyncio task.")
    await deps.task_cancellation_binder.bind_task(
        resolved_primitives.turn_cancellation_id,
        current_task,
        owner=bind_owner,
        metadata={
            "conv_id": resolved_primitives.conv_id,
            "turn_id": resolved_primitives.turn_id,
            "mode": mode,
        },
    )
    return ClaimedAgentTurnState(
        primitives=resolved_primitives,
        turn_record=turn_record,
        todo_state=build_turn_todo_state_from_turn_record(turn_record),
        skill_activation=skill_activation,
        skill_input_claim=skill_input_claim,
    )


async def claim_turn_state_for_known_turn(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    conv_id: str,
    message_index: int,
    user_id: int,
    turn_id: str,
    mode: str,
    max_iterations: int,
    turn_cancellation_id: str,
    todo_state: AgentTurnTodoState,
    initial_active_inference_cancellation_id: str | None,
    bind_owner: str,
) -> ClaimedAgentTurnState:
    primitives = TurnPrimitives(
        start_time=time.monotonic(),
        base_cancellation_id=turn_cancellation_id,
        conv_id=conv_id,
        message_index=message_index,
        user_id=user_id,
        turn_id=turn_id,
        turn_cancellation_id=turn_cancellation_id,
    )
    return await claim_turn_state_from_primitives(
        deps=deps,
        context=context,
        primitives=primitives,
        mode=mode,
        max_iterations=max_iterations,
        todo_state=todo_state,
        initial_active_inference_cancellation_id=initial_active_inference_cancellation_id,
        bind_owner=bind_owner,
    )
