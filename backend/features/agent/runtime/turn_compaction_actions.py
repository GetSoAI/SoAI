"""SoAI - Agent turn context compaction activity flow [backend/features/agent/runtime/turn_compaction_actions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.agent.turn_state_writer import TurnStateWriter
from core.errors.exceptions import SoAIError, ValidationError
from core.events.types_base import Event
from core.openai.tool_message_sequence_repair import (
    repair_openai_tool_message_sequence_for_internal_contracts,
)
from core.tool_calls.context_compaction_boundary_state import (
    build_context_compaction_boundary_state,
)
from features.agent.runtime.auto_compaction_activity_lifecycle import (
    complete_auto_compaction_error_activity,
    complete_auto_compaction_success_activity,
)
from features.agent.runtime.context_compaction.activity_result import (
    AutoCompactionActivityMetadata,
    build_auto_compaction_output_text,
)
from features.agent.runtime.context_compaction.candidates import has_compactable_history
from features.agent.runtime.context_compaction.message_counts import (
    resolve_auto_compaction_message_counts,
)
from features.agent.runtime.context_compaction.service import (
    compact_message_history_with_outcome_if_needed,
    extract_context_summary,
)
from features.agent.runtime.context_compaction.summary import (
    extract_context_compaction_prompt_message,
)
from features.agent.runtime.context_compaction.token_counting import (
    count_compaction_history_occupancy,
)
from features.agent.runtime.tool_sequence_reservations import (
    ToolSequenceIndexReservation,
    build_incremental_tool_sequence_reservation,
)
from features.agent.runtime.turn_compaction_activity import (
    start_auto_compaction_activity,
)
from features.agent.runtime.turn_compaction_activity_scope import (
    build_auto_compaction_activity_scope,
)
from features.agent.runtime.turn_compaction_activity_state import (
    AutoCompactionActivityChronology,
    AutoCompactionActivityState,
    resolve_compaction_model,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.openai.token_accounting import PromptOccupancy
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.tool_calls.protocols import DatabaseToolCallsProtocol
    from core.types.json import JSONDict
    from features.agent.runtime.turn_compaction_activity_scope import (
        AutoCompactionActivityScope,
    )
    from features.agent.runtime.turn_loop_tool_sequences import (
        TurnLoopToolSequenceState,
    )
    from features.agent.session.compaction_budget import ResolvedCompactionBudget

__all__ = ("try_compact_message_history",)


async def try_compact_message_history(
    *,
    message_history: list[JSONDict],
    boundary_source_messages: list[JSONDict],
    base_request_payload: JSONDict,
    prompt_token_counter: PromptTokenCounter,
    token_estimation_profile: TokenEstimationProfile,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
    user_id: int,
    conv_id: str,
    message_index: int,
    turn_id: str,
    iteration_index: int,
    compaction_budget: ResolvedCompactionBudget | None,
    next_action_sequence: Callable[[], Awaitable[int]],
    publish_event: Callable[[Event], Awaitable[None]],
    emit_events: bool,
    turn_state_writer: TurnStateWriter | None = None,
    tool_sequence_state: TurnLoopToolSequenceState | None = None,
    request_context: RequestContext | None = None,
    tool_context: MCPToolContext | None = None,
    database_tool_calls: DatabaseToolCallsProtocol | None = None,
    on_tool_sequence_indexes_reserved: Callable[[ToolSequenceIndexReservation], None] | None = None,
    on_pre_compaction_prompt_occupancy: Callable[[PromptOccupancy], None] | None = None,
    on_compacted_prompt_occupancy: Callable[[PromptOccupancy], None] | None = None,
    on_completed_compaction: (
        Callable[
            [list[JSONDict], AutoCompactionActivityMetadata, str, JSONDict | None],
            None,
        ]
        | None
    ) = None,
) -> list[JSONDict]:
    repaired_history, _changed = repair_openai_tool_message_sequence_for_internal_contracts(
        messages=list(message_history),
    )
    if compaction_budget is None:
        return repaired_history
    occupancy_before = count_compaction_history_occupancy(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=repaired_history,
        token_estimation_profile=token_estimation_profile,
    )
    prompt_tokens_before = occupancy_before.prompt_tokens
    if (
        not occupancy_before.capped
        and int(prompt_tokens_before) <= compaction_budget.trigger_prompt_tokens
    ):
        return repaired_history
    if not has_compactable_history(repaired_history) and (
        int(prompt_tokens_before) <= compaction_budget.maximum_prompt_tokens
    ):
        return repaired_history
    if on_pre_compaction_prompt_occupancy is not None:
        on_pre_compaction_prompt_occupancy(occupancy_before)
    model = resolve_compaction_model(base_request_payload)
    activity: AutoCompactionActivityState | None = None
    activity_scope: AutoCompactionActivityScope | None = None
    if emit_events:
        if turn_state_writer is None:
            raise ValidationError("Auto-compaction event persistence requires a turn_state_writer.")
        if tool_sequence_state is None:
            raise ValidationError(
                "Auto-compaction event persistence requires a shared tool sequence state.",
            )
        if request_context is None or tool_context is None or database_tool_calls is None:
            raise ValidationError("Auto-compaction event persistence requires tool-call context.")
        activity_scope = build_auto_compaction_activity_scope(
            user_id=user_id,
            conv_id=conv_id,
            message_index=message_index,
            turn_id=turn_id,
            iteration_index=iteration_index,
            request_context=request_context,
            tool_context=tool_context,
            database_tool_calls=database_tool_calls,
            next_action_sequence=next_action_sequence,
            publish_event=publish_event,
            turn_state_writer=turn_state_writer,
        )
        chronology = AutoCompactionActivityChronology.from_values(
            content_index_before=tool_sequence_state.content_index_offset,
            thinking_index_before=tool_sequence_state.thinking_index_offset,
            thinking_duration_before_ms=None,
        )
        reserved_sequence_index = tool_sequence_state.allocate_next_sequence_index()
        activity = await start_auto_compaction_activity(
            scope=activity_scope,
            sequence_index=reserved_sequence_index,
            chronology=chronology,
            tool_sequence_state=tool_sequence_state,
        )
        if on_tool_sequence_indexes_reserved is not None:
            on_tool_sequence_indexes_reserved(build_incremental_tool_sequence_reservation(count=1))
    try:
        compaction_outcome = await compact_message_history_with_outcome_if_needed(
            message_history=repaired_history,
            base_request_payload=base_request_payload,
            prompt_token_counter=prompt_token_counter,
            max_prompt_tokens=compaction_budget.target_prompt_tokens,
            maximum_prompt_tokens=compaction_budget.maximum_prompt_tokens,
            summarize_messages=summarize_messages,
            token_estimation_profile=token_estimation_profile,
        )
        compacted = list(compaction_outcome.compacted_messages)
        prompt_tokens_after = compaction_outcome.prompt_occupancy.prompt_tokens
        if compacted == repaired_history or int(prompt_tokens_after) >= int(prompt_tokens_before):
            if activity is None:
                return repaired_history
            raise ValidationError("Auto-compaction did not reduce prompt occupancy.")
        summary_text = extract_context_summary(compacted)
        tool_stub_count, truncated_message_count = resolve_auto_compaction_message_counts(compacted)
        metadata = AutoCompactionActivityMetadata(
            model=model,
            compaction_budget=compaction_budget,
            prompt_tokens_before=prompt_tokens_before,
            prompt_tokens_after=prompt_tokens_after,
            dropped_message_count=max(0, len(repaired_history) - len(compacted)),
            tool_stub_count=tool_stub_count,
            truncated_message_count=truncated_message_count,
            summary_source=compaction_outcome.summary_source,
            boundary_state=build_context_compaction_boundary_state(list(boundary_source_messages)),
        )
        output_text = build_auto_compaction_output_text(
            dropped_message_count=metadata.dropped_message_count,
            tool_stub_count=metadata.tool_stub_count,
            truncated_message_count=metadata.truncated_message_count,
            summary_source=metadata.summary_source,
            summary_text=summary_text,
        )
        prompt_message = extract_context_compaction_prompt_message(compacted)
        if on_compacted_prompt_occupancy is not None:
            on_compacted_prompt_occupancy(compaction_outcome.prompt_occupancy)
        if on_completed_compaction is not None:
            on_completed_compaction(
                list(compacted),
                metadata,
                output_text,
                prompt_message,
            )
        if activity is not None and activity_scope is not None:
            await complete_auto_compaction_success_activity(
                activity=activity,
                scope=activity_scope,
                output_text=output_text,
                prompt_message=prompt_message,
                metadata=metadata,
            )
        return compacted
    except asyncio.CancelledError as exception:
        if activity is not None and activity_scope is not None:
            await complete_auto_compaction_error_activity(
                activity=activity,
                scope=activity_scope,
                exception=exception,
                cancelled=True,
            )
        raise
    except SoAIError as exception:
        if activity is not None and activity_scope is not None:
            await complete_auto_compaction_error_activity(
                activity=activity,
                scope=activity_scope,
                exception=exception,
                cancelled=False,
            )
        raise
