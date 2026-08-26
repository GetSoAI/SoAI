"""SoAI - Manual compaction terminal persistence [backend/features/api/routes/webui/conversation_agent_compaction/message_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.assistant_timeline.tool_result_truncation import (
    truncate_tool_result_payload_for_timeline,
)
from core.database.requests import (
    ManualCompactionAssistantEventRequest,
    ManualCompactionTerminalCommitRequest,
)
from core.errors.exceptions import ValidationError
from core.events.conversation_publication import (
    publish_conversation_updated_and_message_saved,
)
from core.tool_calls.status_values import (
    TOOL_CALL_STATUS_CANCELLED,
    TOOL_CALL_STATUS_COMPLETED,
    TOOL_CALL_STATUS_ERROR,
)
from core.tool_calls.tool_event_payloads import map_tool_call_event_to_tool_payload
from features.api.routes.webui.conversation_agent_compaction.manual_tool_events import (
    build_manual_compaction_tool_completed_event,
)

if TYPE_CHECKING:
    from core.database.requests import ManualCompactionTerminalCommitResult
    from features.api.routes.webui.conversation_agent_compaction.terminal_state import (
        ManualCompactionTerminalOutcome,
    )
    from features.api.runtime.context import ApiContext

__all__ = (
    "PersistedManualCompactionMessage",
    "persist_manual_compaction_terminal_message",
)


@dataclass(frozen=True, slots=True)
class PersistedManualCompactionMessage:
    assistant_at_ms: int
    message_index: int
    message_count: int
    last_modified_at_ms: int
    tool_completion_sequence: int
    turn_terminal_sequence: int


def _resolve_manual_compaction_finish_reason(
    terminal_outcome: ManualCompactionTerminalOutcome,
) -> str:
    if terminal_outcome.status == TOOL_CALL_STATUS_COMPLETED:
        return "stop"
    if terminal_outcome.status == TOOL_CALL_STATUS_CANCELLED:
        return "cancelled"
    if terminal_outcome.status == TOOL_CALL_STATUS_ERROR:
        return "error"
    raise ValidationError("Manual compaction terminal status is invalid.")


def _build_terminal_assistant_event_request(
    *,
    user_id: int,
    conv_id: str,
    turn_id: str,
    iteration_index: int,
    tool_call_id: str,
    started_at_ms: int,
    completed_at_ms: int,
    terminal_outcome: ManualCompactionTerminalOutcome,
) -> ManualCompactionAssistantEventRequest:
    duration_ms = max(0, int(completed_at_ms) - int(started_at_ms))
    completed_payload = map_tool_call_event_to_tool_payload(
        build_manual_compaction_tool_completed_event(
            user_id=int(user_id),
            conv_id=str(conv_id),
            call_id=str(tool_call_id),
            message_index=0,
            status=terminal_outcome.status,
            result=truncate_tool_result_payload_for_timeline(terminal_outcome.result_payload),
            duration_ms=duration_ms,
            error_message=terminal_outcome.error_message,
            turn_id=str(turn_id),
            iteration_index=int(iteration_index),
        ),
    )
    return ManualCompactionAssistantEventRequest(
        sequence=2,
        assistant_revision=3,
        event_type="tool_call_completed",
        tool_payload=completed_payload,
        created_at_ms=int(completed_at_ms),
    )


def _build_persisted_message(
    commit_result: ManualCompactionTerminalCommitResult,
) -> PersistedManualCompactionMessage:
    return PersistedManualCompactionMessage(
        assistant_at_ms=int(commit_result.assistant_at_ms),
        message_index=int(commit_result.message_index),
        message_count=int(commit_result.message_count),
        last_modified_at_ms=int(commit_result.last_modified_at_ms),
        tool_completion_sequence=int(commit_result.tool_completion_sequence),
        turn_terminal_sequence=int(commit_result.turn_terminal_sequence),
    )


async def persist_manual_compaction_terminal_message(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    model_id: str | None,
    assistant_at_ms: int,
    compaction_turn_id: str,
    compaction_iteration_index: int,
    compaction_tool_call_id: str,
    compaction_started_at_ms: int,
    compaction_completed_at_ms: int,
    compaction_terminal_outcome: ManualCompactionTerminalOutcome,
    execution_token: str,
    turn_cancellation_id: str | None,
    error_type: str | None,
    replace_assistant_at_ms: int | None,
    replace_tool_call_id: str | None,
) -> PersistedManualCompactionMessage:
    commit_request = ManualCompactionTerminalCommitRequest(
        conv_id=str(conv_id),
        user_id=int(user_id),
        turn_id=str(compaction_turn_id),
        execution_token=str(execution_token),
        iteration_index=int(compaction_iteration_index),
        tool_call_id=str(compaction_tool_call_id),
        tool_started_at_ms=int(compaction_started_at_ms),
        completed_at_ms=int(compaction_completed_at_ms),
        model_id=model_id,
        assistant_at_ms=int(assistant_at_ms),
        finish_reason=_resolve_manual_compaction_finish_reason(compaction_terminal_outcome),
        terminal_status=compaction_terminal_outcome.status,
        error_message=compaction_terminal_outcome.error_message,
        error_type=error_type,
        turn_cancellation_id=turn_cancellation_id,
        result_payload=compaction_terminal_outcome.result_payload,
        terminal_event=_build_terminal_assistant_event_request(
            user_id=int(user_id),
            conv_id=str(conv_id),
            turn_id=str(compaction_turn_id),
            iteration_index=int(compaction_iteration_index),
            tool_call_id=str(compaction_tool_call_id),
            started_at_ms=int(compaction_started_at_ms),
            completed_at_ms=int(compaction_completed_at_ms),
            terminal_outcome=compaction_terminal_outcome,
        ),
        replace_assistant_at_ms=replace_assistant_at_ms,
        replace_tool_call_id=replace_tool_call_id,
    )
    commit_result = (
        await api_context.dependencies.database_messages.commit_manual_compaction_terminal(
            commit_request,
        )
    )
    persisted_message = _build_persisted_message(commit_result)
    await publish_conversation_updated_and_message_saved(
        api_context.dependencies.event_bus,
        user_id=user_id,
        conv_id=conv_id,
        message_count=int(persisted_message.message_count),
        last_modified_at_ms=int(persisted_message.last_modified_at_ms),
    )
    return persisted_message
