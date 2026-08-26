"""SoAI - Agent turn bootstrap initialization [backend/features/agent/runtime/turn_bootstrap_initialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.status_values import AGENT_TURN_STATUS_RUNNING
from core.agent.turn_record_fields import (
    read_turn_assistant_text,
    read_turn_int,
    read_turn_optional_content_text,
    read_turn_optional_text,
    read_turn_payload_entries,
    read_turn_payload_values,
)
from core.agent.turn_scope_values import TURN_SCOPE_SUBAGENT
from core.agent.turn_state_requests import require_request_context_turn_execution_token
from core.agent.turn_state_writer import TurnStateWriter
from core.runtime.request_context import RequestContext
from features.agent.runtime.turn_bootstrap import AgentTurnBootstrap
from features.agent.runtime.turn_engine import (
    build_action_sequence_tracker,
    build_turn_cancelled_check,
    resolve_turn_primitives,
)
from features.agent.runtime.turn_iteration_policy_types import (
    TurnIterationPolicyConfig,
    TurnIterationPolicyState,
)
from features.agent.runtime.turn_lifecycle.claim_state import (
    claim_turn_state_for_known_turn,
)
from features.agent.runtime.turn_loop_tool_sequences import TurnLoopToolSequenceState
from features.agent.runtime.turn_todo_state import (
    load_turn_todo_state,
    parse_agent_todo_state_payload,
)
from features.agent.session.agent_output_tokens import (
    has_explicit_agent_output_token_cap,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.orchestrator.types import MCPToolContext
    from core.types.json import JSONDict
    from features.agent.runtime.turn_engine import AgentTurnEngineDependencies

__all__ = ("initialize_agent_turn",)


async def initialize_agent_turn(
    *,
    deps: AgentTurnEngineDependencies,
    context: RequestContext,
    tool_context: MCPToolContext,
    settings: AgentSettings,
    base_request_payload: JSONDict,
    turn_id: str | None,
    initial_active_inference_cancellation_id: str | None = None,
) -> AgentTurnBootstrap:
    resolved_turn_id = turn_id
    if resolved_turn_id is None or not resolved_turn_id.strip():
        existing_turn_id = context.agent_turn_id
        if existing_turn_id is not None and existing_turn_id.strip():
            resolved_turn_id = existing_turn_id.strip()
    primitives = resolve_turn_primitives(
        context=context,
        tool_context=tool_context,
        mode=settings.mode,
        turn_id=resolved_turn_id,
    )
    if context.agent_turn_scope == TURN_SCOPE_SUBAGENT:
        todo_state = parse_agent_todo_state_payload(None)
    else:
        todo_state = await load_turn_todo_state(
            database_agent_todo_state=deps.database_agent_todo_state,
            conv_id=primitives.conv_id,
            user_id=primitives.user_id,
        )
    claimed_turn = await claim_turn_state_for_known_turn(
        deps=deps,
        context=context,
        conv_id=primitives.conv_id,
        message_index=primitives.message_index,
        user_id=primitives.user_id,
        turn_id=primitives.turn_id,
        mode=settings.mode,
        max_iterations=settings.max_iterations,
        turn_cancellation_id=primitives.turn_cancellation_id,
        todo_state=todo_state,
        initial_active_inference_cancellation_id=initial_active_inference_cancellation_id,
        bind_owner="agent.turn",
    )
    primitives = claimed_turn.primitives
    initial_turn_state = claimed_turn.turn_record
    todo_state = claimed_turn.todo_state
    sequence_tracker = build_action_sequence_tracker(
        sequencer=deps.agent_chronology_sequencer,
        conv_id=primitives.conv_id,
        user_id=primitives.user_id,
        initial_turn_state=initial_turn_state,
    )
    turn_state_tool_calls = read_turn_payload_entries(initial_turn_state, "tool_calls")
    turn_state_tool_results = read_turn_payload_values(initial_turn_state, "tool_results")
    turn_state_activities = read_turn_payload_entries(initial_turn_state, "activities")
    execution_token = require_request_context_turn_execution_token(
        context,
        operation="agent.turn_bootstrap.initialize_agent_turn",
    )
    turn_state_writer = TurnStateWriter(
        database_agent_turns=deps.database_agent_turns,
        resolve_turn_state_sequence=sequence_tracker.resolve_turn_state_sequence,
        seed_record=dict(initial_turn_state),
        execution_token=execution_token,
        mode=settings.mode,
        max_iterations=settings.max_iterations,
        turn_cancellation_id=primitives.turn_cancellation_id,
        todo_state=todo_state,
        started_at_ms=read_turn_int(initial_turn_state, "started_at_ms") or 0,
        latest_iteration_index=read_turn_int(initial_turn_state, "iteration_index") or 0,
        latest_status=str(initial_turn_state.get("status") or AGENT_TURN_STATUS_RUNNING),
        latest_active_inference_cancellation_id=read_turn_optional_text(
            initial_turn_state,
            "active_inference_cancellation_id",
        ),
        latest_reached_max_iterations=(initial_turn_state.get("reached_max_iterations") is True),
        latest_error_message=read_turn_optional_content_text(
            initial_turn_state,
            "error_message",
        ),
        latest_error_type=read_turn_optional_text(initial_turn_state, "error_type"),
        latest_assistant_text=read_turn_assistant_text(initial_turn_state),
        latest_tool_calls=[dict(entry) for entry in turn_state_tool_calls],
        latest_tool_results=list(turn_state_tool_results),
        latest_activities=[dict(entry) for entry in turn_state_activities],
    )
    tool_sequence_state = TurnLoopToolSequenceState.from_turn_state_writer(turn_state_writer)
    bootstrap = AgentTurnBootstrap(
        deps=deps,
        request_context=context,
        tool_context=tool_context,
        primitives=primitives,
        settings=settings,
        todo_state=todo_state,
        sequence_tracker=sequence_tracker,
        tool_sequence_state=tool_sequence_state,
        turn_state_writer=turn_state_writer,
        turn_cancelled=build_turn_cancelled_check(
            deps.cancellation_history,
            primitives.turn_cancellation_id,
        ),
        iteration_policy_state=TurnIterationPolicyState(
            empty_output_retries=0,
            empty_output_silent_retries=0,
            length_finish_reason_retries=0,
            tool_sequence_retries=0,
            invalid_tool_call_json_retries=0,
            tool_call_protocol_retries=0,
            tool_call_protocol_retry_signature="",
            preview_contract_retries=0,
        ),
        iteration_policy_config=TurnIterationPolicyConfig(
            max_iterations=settings.max_iterations,
            max_empty_output_retries=settings.empty_output_max_retries,
            max_empty_output_silent_retries=settings.empty_output_silent_max_retries,
            max_length_finish_reason_retries=2,
            length_finish_reason_retries_enabled=not has_explicit_agent_output_token_cap(
                base_request_payload,
            ),
            max_tool_sequence_retries=2,
            max_invalid_tool_call_json_retries=2,
            max_tool_call_protocol_retries=3,
            max_preview_contract_retries=settings.preview_contract_max_retries,
        ),
    )
    await bootstrap.publish_turn_started(iteration_index=0)
    return bootstrap
