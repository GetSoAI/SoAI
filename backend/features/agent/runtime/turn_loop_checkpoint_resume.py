"""SoAI - Persisted interaction tool-phase resume [backend/features/agent/runtime/turn_loop_checkpoint_resume.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from features.agent.runtime.turn_iteration_cancellation import (
    resolve_iteration_cancellation_id,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.agent.turn_state_writer import TurnStateWriter
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.agent.runtime.turn_engine import TurnPrimitives

__all__ = ("ResumedToolPhase", "resolve_resumed_tool_phase")


@dataclass(frozen=True, slots=True)
class ResumedToolPhase:
    iteration_index: int
    assistant_text: str | None
    tool_calls: list[JSONDict]
    cancellation_id: str


def resolve_resumed_tool_phase(
    *,
    request_context: RequestContext,
    turn_state_writer: TurnStateWriter,
    primitives: TurnPrimitives,
    settings: AgentSettings,
) -> ResumedToolPhase | None:
    phase = request_context.conversation_input_resume_phase
    if phase is None:
        return None
    if phase not in {
        "before_approved_tool",
        "awaiting_ask_user_result",
        "awaiting_vault_secret",
    }:
        raise StateError("Conversation interaction resume phase is invalid.")
    task_id = request_context.conversation_input_resume_task_id
    tool_call_id = request_context.conversation_input_resume_tool_call_id
    generation = request_context.conversation_input_resume_generation
    iteration_index = request_context.agent_iteration_index
    if task_id is None or tool_call_id is None or generation is None:
        raise StateError("Conversation interaction resume identity is incomplete.")
    if generation <= 0 or iteration_index is None:
        raise StateError("Conversation interaction resume identity is incomplete.")
    if iteration_index != turn_state_writer.latest_iteration_index:
        raise StateError("Conversation interaction resume identity is incomplete.")
    tool_calls = [dict(call) for call in turn_state_writer.latest_tool_calls]
    completed_count = len(turn_state_writer.latest_tool_results)
    if completed_count >= len(tool_calls):
        raise StateError("Conversation interaction resume has no pending tool call.")
    if tool_calls[completed_count].get("id") != tool_call_id:
        raise StateError("Conversation interaction resume tool identity is stale.")
    cancellation_id = resolve_iteration_cancellation_id(
        turn_state_writer=turn_state_writer,
        iteration_index=iteration_index,
        primitives=primitives,
        settings=settings,
    )
    return ResumedToolPhase(
        iteration_index=iteration_index,
        assistant_text=turn_state_writer.latest_assistant_text,
        tool_calls=tool_calls,
        cancellation_id=cancellation_id,
    )
