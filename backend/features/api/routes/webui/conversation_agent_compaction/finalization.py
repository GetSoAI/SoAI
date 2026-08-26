"""SoAI - Manual compaction finalization helpers [backend/features/api/routes/webui/conversation_agent_compaction/finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.logging.protocols import LoggerProtocol
from core.types.json import JSONDict
from features.api.routes.webui.conversation_agent_compaction.execution_identity import (
    ManualCompactionExecutionIdentity,
)
from features.api.routes.webui.conversation_agent_compaction.message_persistence import (
    persist_manual_compaction_terminal_message,
)
from features.api.routes.webui.conversation_agent_compaction.terminal_state import (
    build_manual_compaction_terminal_outcome,
    normalize_manual_compaction_terminal_status,
)
from features.api.routes.webui.conversation_agent_compaction.turn_state import (
    publish_manual_compaction_failure,
    publish_manual_compaction_success,
)
from features.api.runtime.context import ApiContext

__all__ = (
    "finalize_manual_compaction_failure",
    "finalize_manual_compaction_success",
)


async def finalize_manual_compaction_success(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    conv_id: str,
    user_id: int,
    turn_id: str,
    iteration_index: int,
    tool_call_id: str,
    tool_started_at_ms: int,
    execution_token: str,
    turn_cancellation_id: str | None,
    completed_at_ms: int,
    model_id: str | None,
    assistant_at_ms: int,
    activity_output_text: str,
    activity_prompt_message: JSONDict | None,
    tool_result_details: JSONDict,
    replace_assistant_at_ms: int | None,
    replace_tool_call_id: str | None,
) -> None:
    execution_identity = ManualCompactionExecutionIdentity(
        conv_id=str(conv_id),
        user_id=int(user_id),
        turn_id=str(turn_id),
        iteration_index=int(iteration_index),
        tool_call_id=str(tool_call_id),
        tool_started_at_ms=int(tool_started_at_ms),
    )
    terminal_outcome = build_manual_compaction_terminal_outcome(
        status="completed",
        result_text=str(activity_output_text or ""),
        prompt_message=activity_prompt_message,
        error_message=None,
        result_details=tool_result_details,
    )
    persisted_message = await persist_manual_compaction_terminal_message(
        api_context=api_context,
        conv_id=str(conv_id),
        user_id=int(user_id),
        model_id=model_id,
        assistant_at_ms=int(assistant_at_ms),
        compaction_turn_id=str(turn_id),
        compaction_iteration_index=int(iteration_index),
        compaction_tool_call_id=str(tool_call_id),
        compaction_started_at_ms=int(tool_started_at_ms),
        compaction_completed_at_ms=int(completed_at_ms),
        compaction_terminal_outcome=terminal_outcome,
        execution_token=str(execution_token),
        turn_cancellation_id=turn_cancellation_id,
        error_type=None,
        replace_assistant_at_ms=replace_assistant_at_ms,
        replace_tool_call_id=replace_tool_call_id,
    )
    await publish_manual_compaction_success(
        api_context=api_context,
        logger=logger,
        identity=execution_identity,
        message_index=int(persisted_message.message_index),
        completed_at_ms=int(completed_at_ms),
        tool_completion_sequence=int(persisted_message.tool_completion_sequence),
        turn_terminal_sequence=int(persisted_message.turn_terminal_sequence),
        terminal_outcome=terminal_outcome,
    )


async def finalize_manual_compaction_failure(
    *,
    api_context: ApiContext,
    logger: LoggerProtocol,
    conv_id: str,
    user_id: int,
    turn_id: str,
    iteration_index: int,
    tool_call_id: str,
    tool_started_at_ms: int,
    execution_token: str,
    turn_cancellation_id: str | None,
    completed_at_ms: int,
    model_id: str | None,
    assistant_at_ms: int,
    failure_status: str,
    activity_output_text: str,
    activity_prompt_message: JSONDict | None,
    error_message: str,
    error_type: str,
    tool_result_details: JSONDict,
    replace_assistant_at_ms: int | None,
    replace_tool_call_id: str | None,
) -> None:
    execution_identity = ManualCompactionExecutionIdentity(
        conv_id=str(conv_id),
        user_id=int(user_id),
        turn_id=str(turn_id),
        iteration_index=int(iteration_index),
        tool_call_id=str(tool_call_id),
        tool_started_at_ms=int(tool_started_at_ms),
    )
    normalized_error_message = str(error_message or "")
    normalized_error_type = str(error_type or "")
    if not normalized_error_message.strip() or not normalized_error_type.strip():
        raise ValidationError("Manual compaction failure requires an error message and type.")
    normalized_failure_status = normalize_manual_compaction_terminal_status(failure_status)
    terminal_outcome = build_manual_compaction_terminal_outcome(
        status=normalized_failure_status,
        result_text=str(activity_output_text or ""),
        prompt_message=activity_prompt_message,
        error_message=normalized_error_message,
        result_details=tool_result_details,
    )
    persisted_message = await persist_manual_compaction_terminal_message(
        api_context=api_context,
        conv_id=str(conv_id),
        user_id=int(user_id),
        model_id=model_id,
        assistant_at_ms=int(assistant_at_ms),
        compaction_turn_id=str(turn_id),
        compaction_iteration_index=int(iteration_index),
        compaction_tool_call_id=str(tool_call_id),
        compaction_started_at_ms=int(tool_started_at_ms),
        compaction_completed_at_ms=int(completed_at_ms),
        compaction_terminal_outcome=terminal_outcome,
        execution_token=str(execution_token),
        turn_cancellation_id=turn_cancellation_id,
        error_type=normalized_error_type,
        replace_assistant_at_ms=replace_assistant_at_ms,
        replace_tool_call_id=replace_tool_call_id,
    )

    await publish_manual_compaction_failure(
        api_context=api_context,
        logger=logger,
        identity=execution_identity,
        message_index=int(persisted_message.message_index),
        completed_at_ms=int(completed_at_ms),
        tool_completion_sequence=int(persisted_message.tool_completion_sequence),
        turn_terminal_sequence=int(persisted_message.turn_terminal_sequence),
        error_message=normalized_error_message,
        error_type=normalized_error_type,
        terminal_outcome=terminal_outcome,
    )
