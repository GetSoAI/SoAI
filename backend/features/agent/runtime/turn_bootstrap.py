"""SoAI - Shared agent turn bootstrap state [backend/features/agent/runtime/turn_bootstrap.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.agent.turn_state_writer import TurnStateWriter
from core.events.types_base import Event
from core.openai.pinned_prefix import split_leading_pinned_prefix
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_COMPLETED,
    is_active_tool_call_status,
)
from features.agent.events.types import AgentTurnStartedEvent
from features.agent.runtime.context_compaction.summary import is_context_summary_message
from features.agent.runtime.tool_sequence_reservations import (
    ToolSequenceIndexReservation,
    build_incremental_tool_sequence_reservation,
    build_replayed_tool_sequence_reservation,
)
from features.agent.runtime.turn_bootstrap_auto_compaction_selection import (
    select_initial_auto_compaction_activity,
)
from features.agent.runtime.turn_compaction_actions import try_compact_message_history
from features.agent.runtime.turn_compaction_activity import (
    start_auto_compaction_activity,
)
from features.agent.runtime.turn_compaction_activity_completion import (
    complete_auto_compaction_activity,
)
from features.agent.runtime.turn_compaction_activity_resume import (
    resume_auto_compaction_activity,
)
from features.agent.runtime.turn_compaction_activity_scope import (
    build_auto_compaction_activity_scope,
)
from features.agent.runtime.turn_compaction_activity_state import (
    AutoCompactionActivityChronology,
    require_auto_compaction_sequence_index,
)
from features.agent.runtime.turn_engine import (
    ActionSequenceTracker,
    publish_agent_event,
)
from features.agent.runtime.turn_iteration_policy_types import (
    TurnIterationPolicyConfig,
    TurnIterationPolicyState,
)
from features.agent.session.compaction_budget import (
    resolve_compaction_budget_from_agent_settings,
)

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.agent.todo_state_models import AgentTurnTodoState
    from core.openai.token_accounting import PromptOccupancy
    from core.orchestrator.types import MCPToolContext
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.agent.runtime.context_compaction.activity_result import (
        PreparedAutoCompactionSnapshot,
    )
    from features.agent.runtime.turn_compaction_activity_scope import (
        AutoCompactionActivityScope,
    )
    from features.agent.runtime.turn_engine import (
        AgentTurnEngineDependencies,
        TurnPrimitives,
    )
    from features.agent.runtime.turn_loop_tool_sequences import (
        TurnLoopToolSequenceState,
    )

__all__ = ("AgentTurnBootstrap",)


@dataclass(slots=True)
class AgentTurnBootstrap:
    deps: AgentTurnEngineDependencies
    request_context: RequestContext
    tool_context: MCPToolContext
    primitives: TurnPrimitives
    settings: AgentSettings
    todo_state: AgentTurnTodoState
    sequence_tracker: ActionSequenceTracker
    tool_sequence_state: TurnLoopToolSequenceState
    turn_state_writer: TurnStateWriter
    turn_cancelled: Callable[[], Awaitable[bool]]
    iteration_policy_state: TurnIterationPolicyState
    iteration_policy_config: TurnIterationPolicyConfig

    def _resolve_initial_auto_compaction_activity(self) -> JSONDict | None:
        return select_initial_auto_compaction_activity(
            activities=self.turn_state_writer.latest_activities,
            current_turn_id=str(self.primitives.turn_id),
        )

    def _reserve_existing_auto_compaction_streaming_offset(
        self,
        persisted_activity: JSONDict,
        on_tool_sequence_indexes_reserved: Callable[[ToolSequenceIndexReservation], None] | None,
    ) -> None:
        if on_tool_sequence_indexes_reserved is None:
            return
        sequence_index = require_auto_compaction_sequence_index(persisted_activity)
        on_tool_sequence_indexes_reserved(
            build_replayed_tool_sequence_reservation(
                next_sequence_index=sequence_index + 1,
            ),
        )

    def _build_auto_compaction_scope(self, *, iteration_index: int) -> AutoCompactionActivityScope:
        return build_auto_compaction_activity_scope(
            user_id=self.primitives.user_id,
            conv_id=self.primitives.conv_id,
            message_index=self.primitives.message_index,
            turn_id=self.primitives.turn_id,
            iteration_index=iteration_index,
            request_context=self.request_context,
            tool_context=self.tool_context,
            database_tool_calls=self.deps.database_tool_calls,
            next_action_sequence=self.sequence_tracker.next_sequence,
            publish_event=self.emit_event,
            turn_state_writer=self.turn_state_writer,
        )

    async def emit_event(self, event_obj: Event) -> None:
        await publish_agent_event(
            event_bus=self.deps.event_bus,
            logger=self.deps.logger,
            event_obj=event_obj,
        )

    async def publish_turn_started(self, *, iteration_index: int) -> None:
        await self.emit_event(
            AgentTurnStartedEvent(
                user_id=self.primitives.user_id,
                conv_id=self.primitives.conv_id,
                turn_id=self.primitives.turn_id,
                iteration_index=int(iteration_index),
                sequence=await self.sequence_tracker.next_sequence(),
                mode=self.settings.mode,
                max_iterations=self.settings.max_iterations,
            ),
        )

    async def compact_initial_messages(
        self,
        *,
        message_history: list[JSONDict],
        boundary_source_messages: list[JSONDict],
        base_request_payload: JSONDict,
        summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
        prepared_auto_compaction: PreparedAutoCompactionSnapshot | None = None,
        on_tool_sequence_indexes_reserved: (
            Callable[[ToolSequenceIndexReservation], None] | None
        ) = None,
        on_pre_compaction_prompt_occupancy: Callable[[PromptOccupancy], None] | None = None,
        on_compacted_prompt_occupancy: Callable[[PromptOccupancy], None] | None = None,
    ) -> list[JSONDict]:
        if prepared_auto_compaction is not None:
            if on_compacted_prompt_occupancy is not None:
                on_compacted_prompt_occupancy(prepared_auto_compaction.prompt_occupancy)
            persisted_activity = self._resolve_initial_auto_compaction_activity()
            if persisted_activity is not None:
                status_value = persisted_activity.get("status")
                status = status_value.strip() if isinstance(status_value, str) else ""
                if status == TOOL_CALL_STATUS_COMPLETED:
                    self._reserve_existing_auto_compaction_streaming_offset(
                        persisted_activity,
                        on_tool_sequence_indexes_reserved,
                    )
                    return [
                        dict(message) for message in prepared_auto_compaction.compacted_messages
                    ]
                if is_active_tool_call_status(status):
                    activity_scope = self._build_auto_compaction_scope(iteration_index=0)
                    resumed_activity = await resume_auto_compaction_activity(
                        persisted_activity=persisted_activity,
                        scope=activity_scope,
                    )
                    if on_tool_sequence_indexes_reserved is not None:
                        on_tool_sequence_indexes_reserved(
                            build_replayed_tool_sequence_reservation(
                                next_sequence_index=resumed_activity.sequence_index + 1,
                            ),
                        )
                    await complete_auto_compaction_activity(
                        activity=resumed_activity,
                        scope=activity_scope,
                        status=TOOL_CALL_STATUS_COMPLETED,
                        output_text=prepared_auto_compaction.output_text,
                        prompt_message=prepared_auto_compaction.prompt_message,
                        error_message=None,
                        metadata=prepared_auto_compaction.metadata,
                    )
                    return [
                        dict(message) for message in prepared_auto_compaction.compacted_messages
                    ]
            reserved_sequence_index = self.tool_sequence_state.allocate_next_sequence_index()
            activity_scope = self._build_auto_compaction_scope(iteration_index=0)
            activity = await start_auto_compaction_activity(
                scope=activity_scope,
                sequence_index=reserved_sequence_index,
                chronology=AutoCompactionActivityChronology.empty(),
                tool_sequence_state=self.tool_sequence_state,
            )
            if on_tool_sequence_indexes_reserved is not None:
                on_tool_sequence_indexes_reserved(
                    build_incremental_tool_sequence_reservation(count=1),
                )
            await complete_auto_compaction_activity(
                activity=activity,
                scope=activity_scope,
                status=TOOL_CALL_STATUS_COMPLETED,
                output_text=prepared_auto_compaction.output_text,
                prompt_message=prepared_auto_compaction.prompt_message,
                error_message=None,
                metadata=prepared_auto_compaction.metadata,
            )
            return [dict(message) for message in prepared_auto_compaction.compacted_messages]
        boundary_source_messages = split_leading_pinned_prefix(
            boundary_source_messages,
            stop_before=is_context_summary_message,
        )[1]
        compaction_budget = resolve_compaction_budget_from_agent_settings(self.settings)
        compacted_messages = await try_compact_message_history(
            message_history=message_history,
            boundary_source_messages=boundary_source_messages,
            base_request_payload=base_request_payload,
            prompt_token_counter=self.deps.prompt_token_counter,
            token_estimation_profile=self.settings.token_estimation_profile,
            summarize_messages=summarize_messages,
            user_id=self.primitives.user_id,
            conv_id=self.primitives.conv_id,
            message_index=self.primitives.message_index,
            turn_id=self.primitives.turn_id,
            iteration_index=0,
            compaction_budget=compaction_budget,
            next_action_sequence=self.sequence_tracker.next_sequence,
            publish_event=self.emit_event,
            emit_events=True,
            turn_state_writer=self.turn_state_writer,
            tool_sequence_state=self.tool_sequence_state,
            request_context=self.request_context,
            tool_context=self.tool_context,
            database_tool_calls=self.deps.database_tool_calls,
            on_tool_sequence_indexes_reserved=on_tool_sequence_indexes_reserved,
            on_pre_compaction_prompt_occupancy=on_pre_compaction_prompt_occupancy,
            on_compacted_prompt_occupancy=on_compacted_prompt_occupancy,
        )
        return compacted_messages
