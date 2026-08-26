"""SoAI - Manual compaction start event publishing [backend/features/api/routes/webui/conversation_agent_compaction/start_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.database.requests import (
    ManualCompactionAssistantEventRequest,
    ManualCompactionStartCommitRequest,
)
from core.logging.protocols import LoggerProtocol
from core.tool_calls.tool_event_payloads import map_tool_call_event_to_tool_payload
from features.agent.events.types import (
    AgentTurnStartedEvent,
)
from features.agent.runtime.turn_engine import publish_agent_event
from features.api.routes.webui.conversation_agent_compaction.manual_tool_events import (
    build_manual_compaction_tool_created_event,
    build_manual_compaction_tool_created_event_for_values,
    build_manual_compaction_tool_started_event,
    build_manual_compaction_tool_started_event_for_values,
)
from features.api.routes.webui.conversation_agent_compaction.start_state_claims import (
    ManualCompactionStartState,
)

if TYPE_CHECKING:
    from core.database.requests import ManualCompactionStartCommitResult
    from features.api.runtime.context import ApiContext
    from features.api.runtime.current_user import CurrentUser

__all__ = ("publish_manual_compaction_start_events",)


async def publish_manual_compaction_start_events(
    api_context: ApiContext,
    current_user: CurrentUser,
    start_state: ManualCompactionStartState,
    logger: LoggerProtocol,
) -> ManualCompactionStartCommitResult:
    start_result = await api_context.dependencies.database_messages.commit_manual_compaction_start(
        ManualCompactionStartCommitRequest(
            conv_id=start_state.conv_id,
            user_id=int(current_user["id"]),
            turn_id=start_state.turn_id,
            execution_token=start_state.execution_token,
            iteration_index=int(start_state.iteration_index),
            tool_call_id=start_state.tool_call_id,
            requested_started_at_ms=int(start_state.started_at_ms),
            model_id=start_state.model,
            mode=start_state.mode,
            max_iterations=1,
            turn_cancellation_id=start_state.turn_cancellation_id,
            assistant_events=_build_start_assistant_events(
                user_id=int(current_user["id"]),
                start_state=start_state,
            ),
            replace_assistant_at_ms=start_state.replace_assistant_at_ms,
            replace_tool_call_id=start_state.replace_tool_call_id,
        ),
    )
    await publish_agent_event(
        event_bus=api_context.dependencies.event_bus,
        logger=logger,
        event_obj=AgentTurnStartedEvent(
            user_id=current_user["id"],
            conv_id=start_state.conv_id,
            turn_id=start_state.turn_id,
            iteration_index=start_state.iteration_index,
            sequence=int(start_result.turn_started_sequence),
            mode=start_state.mode,
            max_iterations=1,
        ),
    )
    await publish_agent_event(
        event_bus=api_context.dependencies.event_bus,
        logger=logger,
        event_obj=build_manual_compaction_tool_created_event(
            user_id=current_user["id"],
            start_state=start_state,
            message_index=int(start_result.message_index),
            sequence_index=int(start_result.tool_created_sequence),
        ),
    )
    await publish_agent_event(
        event_bus=api_context.dependencies.event_bus,
        logger=logger,
        event_obj=build_manual_compaction_tool_started_event(
            user_id=current_user["id"],
            start_state=start_state,
            message_index=int(start_result.message_index),
            sequence_index=int(start_result.tool_started_sequence),
            started_at_ms=int(start_result.assistant_at_ms),
        ),
    )
    return start_result


def _build_start_assistant_events(
    *,
    user_id: int,
    start_state: ManualCompactionStartState,
) -> tuple[ManualCompactionAssistantEventRequest, ...]:
    created_payload = map_tool_call_event_to_tool_payload(
        build_manual_compaction_tool_created_event_for_values(
            user_id=user_id,
            conv_id=start_state.conv_id,
            call_id=start_state.tool_call_id,
            message_index=0,
            turn_id=start_state.turn_id,
            iteration_index=int(start_state.iteration_index),
        ),
    )
    started_payload = map_tool_call_event_to_tool_payload(
        build_manual_compaction_tool_started_event_for_values(
            user_id=user_id,
            conv_id=start_state.conv_id,
            call_id=start_state.tool_call_id,
            message_index=0,
            started_at_ms=int(start_state.started_at_ms),
            turn_id=start_state.turn_id,
            iteration_index=int(start_state.iteration_index),
        ),
    )
    return (
        ManualCompactionAssistantEventRequest(
            sequence=0,
            assistant_revision=1,
            event_type="tool_call_created",
            tool_payload=created_payload,
            created_at_ms=int(start_state.started_at_ms),
        ),
        ManualCompactionAssistantEventRequest(
            sequence=1,
            assistant_revision=2,
            event_type="tool_call_started",
            tool_payload=started_payload,
            created_at_ms=int(start_state.started_at_ms),
        ),
    )
