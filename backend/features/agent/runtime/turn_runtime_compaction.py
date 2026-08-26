"""SoAI - Agent turn runtime compaction callbacks [backend/features/agent/runtime/turn_runtime_compaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.openai.pinned_prefix import split_leading_pinned_prefix
from features.agent.runtime.context_compaction.summary import is_context_summary_message
from features.agent.runtime.turn_compaction_actions import try_compact_message_history
from features.agent.runtime.turn_loop_models import TurnLoopCompactionResult
from features.agent.session.compaction_budget import (
    resolve_compaction_budget_from_agent_settings,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.openai.token_accounting import PromptOccupancy
    from core.types.json import JSONDict
    from features.agent.runtime.tool_sequence_reservations import (
        ToolSequenceIndexReservation,
    )
    from features.agent.runtime.turn_bootstrap import AgentTurnBootstrap
    from features.agent.runtime.turn_engine import AgentTurnEngineDependencies

__all__ = ("build_runtime_compaction_callback",)


def build_runtime_compaction_callback(
    *,
    deps: AgentTurnEngineDependencies,
    bootstrap: AgentTurnBootstrap,
    base_request_payload: JSONDict,
    settings: AgentSettings,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
    on_tool_sequence_indexes_reserved: Callable[[ToolSequenceIndexReservation], None] | None,
    on_pre_compaction_prompt_occupancy: Callable[[PromptOccupancy], None] | None,
    on_compacted_prompt_occupancy: Callable[[PromptOccupancy], None] | None,
) -> Callable[[int, list[JSONDict], list[JSONDict]], Awaitable[TurnLoopCompactionResult]]:
    compaction_budget = resolve_compaction_budget_from_agent_settings(settings)

    async def compact_messages(
        iteration_index: int,
        current_history: list[JSONDict],
        current_boundary_source_messages: list[JSONDict],
    ) -> TurnLoopCompactionResult:
        boundary_source_messages = split_leading_pinned_prefix(
            current_boundary_source_messages,
            stop_before=is_context_summary_message,
        )[1]
        compacted_messages = await try_compact_message_history(
            message_history=current_history,
            boundary_source_messages=boundary_source_messages,
            base_request_payload=base_request_payload,
            prompt_token_counter=deps.prompt_token_counter,
            token_estimation_profile=bootstrap.settings.token_estimation_profile,
            summarize_messages=summarize_messages,
            user_id=bootstrap.primitives.user_id,
            conv_id=bootstrap.primitives.conv_id,
            message_index=bootstrap.primitives.message_index,
            turn_id=bootstrap.primitives.turn_id,
            iteration_index=iteration_index,
            compaction_budget=compaction_budget,
            next_action_sequence=bootstrap.sequence_tracker.next_sequence,
            publish_event=bootstrap.emit_event,
            emit_events=True,
            turn_state_writer=bootstrap.turn_state_writer,
            tool_sequence_state=bootstrap.tool_sequence_state,
            request_context=bootstrap.request_context,
            tool_context=bootstrap.tool_context,
            database_tool_calls=deps.database_tool_calls,
            on_tool_sequence_indexes_reserved=on_tool_sequence_indexes_reserved,
            on_pre_compaction_prompt_occupancy=on_pre_compaction_prompt_occupancy,
            on_compacted_prompt_occupancy=on_compacted_prompt_occupancy,
        )
        return TurnLoopCompactionResult(
            prompt_messages=[dict(message) for message in compacted_messages],
            boundary_source_messages=[dict(message) for message in compacted_messages],
        )

    return compact_messages
