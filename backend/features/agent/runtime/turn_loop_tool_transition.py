"""SoAI - Agent turn-loop transition after tool execution [backend/features/agent/runtime/turn_loop_tool_transition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from features.agent.runtime.openai_payload import (
    complete_assistant_tool_calls_as_stopped,
)
from features.agent.runtime.tool_execution_steer_interrupt import (
    AgentTurnInterruptedBySteer,
)
from features.agent.runtime.turn_iteration_policy_types import (
    AgentOutputPublicationMode,
    is_next_iteration_blocked,
)
from features.agent.runtime.turn_loop_compaction_transition import (
    compact_turn_loop_history,
)
from features.agent.runtime.turn_loop_tool_phase import execute_turn_tool_phase
from features.agent.runtime.turn_terminal_state import (
    TurnTerminalOutcome,
    build_cancelled_turn_terminal_outcome,
    build_interrupted_turn_terminal_outcome,
    build_max_iterations_turn_terminal_outcome,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.openai.token_counter import PromptTokenCounter
    from core.types.json import JSONDict
    from features.agent.runtime.tool_phase_execution_context import (
        ToolPhaseExecutionContext,
    )
    from features.agent.runtime.turn_loop_models import TurnLoopCompactionCallback

__all__ = ("TurnLoopToolTransition", "advance_turn_loop_after_tools")


@dataclass(frozen=True, slots=True)
class TurnLoopToolTransition:
    iteration_index: int
    message_history: list[JSONDict]
    boundary_source_messages: list[JSONDict]
    total_tool_calls: int
    output_publication_mode: AgentOutputPublicationMode
    terminal_outcome: TurnTerminalOutcome | None
    completed: bool


async def advance_turn_loop_after_tools(
    *,
    phase_context: ToolPhaseExecutionContext,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    settings: AgentSettings,
    compact_messages: TurnLoopCompactionCallback,
    final_payload: JSONDict,
    total_tool_calls: int,
    output_publication_mode: AgentOutputPublicationMode,
) -> TurnLoopToolTransition:
    try:
        tool_phase_outcome = await execute_turn_tool_phase(
            phase_context=phase_context,
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            settings=settings,
        )
    except AgentTurnInterruptedBySteer as exception:
        return TurnLoopToolTransition(
            iteration_index=phase_context.iteration_index,
            message_history=phase_context.message_history,
            boundary_source_messages=phase_context.boundary_source_messages,
            total_tool_calls=total_tool_calls + max(0, exception.executed_tool_calls),
            output_publication_mode=output_publication_mode,
            terminal_outcome=build_interrupted_turn_terminal_outcome(str(exception)),
            completed=True,
        )
    next_total_tool_calls = total_tool_calls + tool_phase_outcome.tool_results_count
    if await phase_context.turn_cancelled():
        return TurnLoopToolTransition(
            iteration_index=phase_context.iteration_index,
            message_history=phase_context.message_history,
            boundary_source_messages=phase_context.boundary_source_messages,
            total_tool_calls=next_total_tool_calls,
            output_publication_mode=output_publication_mode,
            terminal_outcome=build_cancelled_turn_terminal_outcome(),
            completed=True,
        )
    if tool_phase_outcome.stop_requested:
        complete_assistant_tool_calls_as_stopped(
            final_payload,
            assistant_text=phase_context.assistant_text,
        )
        return TurnLoopToolTransition(
            iteration_index=phase_context.iteration_index,
            message_history=phase_context.message_history,
            boundary_source_messages=phase_context.boundary_source_messages,
            total_tool_calls=next_total_tool_calls,
            output_publication_mode=output_publication_mode,
            terminal_outcome=None,
            completed=True,
        )
    if is_next_iteration_blocked(
        iteration_index=phase_context.iteration_index,
        max_iterations=settings.max_iterations,
    ):
        return TurnLoopToolTransition(
            iteration_index=phase_context.iteration_index,
            message_history=phase_context.message_history,
            boundary_source_messages=phase_context.boundary_source_messages,
            total_tool_calls=next_total_tool_calls,
            output_publication_mode=output_publication_mode,
            terminal_outcome=build_max_iterations_turn_terminal_outcome(),
            completed=True,
        )
    message_history, boundary_source_messages = await compact_turn_loop_history(
        compact_messages=compact_messages,
        iteration_index=phase_context.iteration_index,
        message_history=phase_context.message_history,
        boundary_source_messages=phase_context.boundary_source_messages,
    )
    return TurnLoopToolTransition(
        iteration_index=phase_context.iteration_index + 1,
        message_history=message_history,
        boundary_source_messages=boundary_source_messages,
        total_tool_calls=next_total_tool_calls,
        output_publication_mode=output_publication_mode,
        terminal_outcome=None,
        completed=False,
    )
