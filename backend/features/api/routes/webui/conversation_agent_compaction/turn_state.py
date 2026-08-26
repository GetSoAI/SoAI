"""SoAI - Manual compaction terminal event publication [backend/features/api/routes/webui/conversation_agent_compaction/turn_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from features.agent.events.types import (
    AgentTurnCompletedEvent,
    AgentTurnErrorEvent,
)
from features.agent.runtime.turn_engine import publish_agent_event
from features.api.routes.webui.conversation_agent_compaction.execution_identity import (
    ManualCompactionExecutionIdentity,
)
from features.api.routes.webui.conversation_agent_compaction.manual_tool_events import (
    build_manual_compaction_tool_completed_event,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.api.routes.webui.conversation_agent_compaction.terminal_state import (
        ManualCompactionTerminalOutcome,
    )
    from features.api.runtime.context import ApiContext

__all__ = (
    "publish_manual_compaction_failure",
    "publish_manual_compaction_success",
    "publish_manual_compaction_terminal_state",
)


async def _publish_terminal_state(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    identity: ManualCompactionExecutionIdentity,
    message_index: int,
    completed_at_ms: int,
    tool_completion_sequence: int,
    terminal_outcome: ManualCompactionTerminalOutcome,
) -> None:
    await publish_manual_compaction_terminal_state(
        api_context=api_context,
        logger=logger,
        conv_id=identity.conv_id,
        user_id=identity.user_id,
        turn_id=identity.turn_id,
        iteration_index=identity.iteration_index,
        tool_call_id=identity.tool_call_id,
        tool_started_at_ms=identity.tool_started_at_ms,
        message_index=message_index,
        completed_at_ms=completed_at_ms,
        tool_completion_sequence=tool_completion_sequence,
        terminal_outcome=terminal_outcome,
    )


async def publish_manual_compaction_failure(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    identity: ManualCompactionExecutionIdentity,
    message_index: int,
    completed_at_ms: int,
    tool_completion_sequence: int,
    turn_terminal_sequence: int,
    error_message: str,
    error_type: str,
    terminal_outcome: ManualCompactionTerminalOutcome,
) -> None:
    await _publish_terminal_state(
        api_context=api_context,
        logger=logger,
        identity=identity,
        message_index=message_index,
        completed_at_ms=completed_at_ms,
        tool_completion_sequence=tool_completion_sequence,
        terminal_outcome=terminal_outcome,
    )
    await publish_agent_event(
        event_bus=api_context.dependencies.event_bus,
        logger=logger,
        event_obj=AgentTurnErrorEvent(
            user_id=identity.user_id,
            conv_id=identity.conv_id,
            turn_id=identity.turn_id,
            iteration_index=identity.iteration_index,
            sequence=int(turn_terminal_sequence),
            message=error_message,
            error_type=error_type,
        ),
    )


async def publish_manual_compaction_success(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    identity: ManualCompactionExecutionIdentity,
    message_index: int,
    completed_at_ms: int,
    tool_completion_sequence: int,
    turn_terminal_sequence: int,
    terminal_outcome: ManualCompactionTerminalOutcome,
) -> None:
    await _publish_terminal_state(
        api_context=api_context,
        logger=logger,
        identity=identity,
        message_index=message_index,
        completed_at_ms=completed_at_ms,
        tool_completion_sequence=tool_completion_sequence,
        terminal_outcome=terminal_outcome,
    )
    await publish_agent_event(
        event_bus=api_context.dependencies.event_bus,
        logger=logger,
        event_obj=AgentTurnCompletedEvent(
            user_id=identity.user_id,
            conv_id=identity.conv_id,
            turn_id=identity.turn_id,
            iteration_index=identity.iteration_index,
            sequence=int(turn_terminal_sequence),
            total_iterations=identity.iteration_index + 1,
            reached_max_iterations=False,
        ),
    )


async def publish_manual_compaction_terminal_state(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    conv_id: str,
    user_id: int,
    turn_id: str,
    iteration_index: int,
    tool_call_id: str,
    tool_started_at_ms: int,
    message_index: int,
    completed_at_ms: int,
    tool_completion_sequence: int,
    terminal_outcome: ManualCompactionTerminalOutcome,
) -> None:
    duration_ms = max(0, int(completed_at_ms) - int(tool_started_at_ms))
    await publish_agent_event(
        event_bus=api_context.dependencies.event_bus,
        logger=logger,
        event_obj=build_manual_compaction_tool_completed_event(
            user_id=user_id,
            conv_id=conv_id,
            call_id=tool_call_id,
            message_index=message_index,
            status=terminal_outcome.status,
            result=terminal_outcome.result_payload,
            duration_ms=int(duration_ms),
            error_message=terminal_outcome.error_message,
            turn_id=turn_id,
            iteration_index=iteration_index,
            sequence_index=int(tool_completion_sequence),
        ),
    )
