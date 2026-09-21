"""SoAI - Chat stream start conversation validation [backend/features/api/routes/system/events/chat_stream/start_command_conversation_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from core.conversations.conversation_start_snapshot import ConversationStartSnapshot
from core.errors.exceptions import ValidationError
from core.validation.epoch import is_unix_epoch_ms
from features.api.routes.system.events.chat_stream.command_errors import (
    enqueue_chat_stream_start_error,
)
from features.api.routes.system.events.chat_stream.start_command_invalid_request_reporting import (
    report_invalid_start_assistant_at_ms,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.api.runtime.context import ApiContext
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "ConversationStartValidationFailure",
    "require_conversation_and_timestamp_ok",
    "resolve_conversation_start_snapshot",
)


@dataclass(frozen=True, slots=True)
class ConversationStartValidationFailure:
    code: str
    message: str
    invalid_assistant_timestamp: bool
    snapshot: ConversationStartSnapshot | None = None


def validate_assistant_at_ms(
    *,
    latest_message_timestamp: int | None,
    assistant_at_ms: int,
) -> None:
    if latest_message_timestamp is not None and not is_unix_epoch_ms(
        latest_message_timestamp,
        enforce_maximum=False,
    ):
        raise ValidationError(
            "Stored conversation message timestamp must be an epoch-millisecond integer.",
        )
    if latest_message_timestamp is not None and assistant_at_ms <= latest_message_timestamp:
        raise ValidationError(
            "assistant_at_ms must be strictly greater than the latest stored conversation message timestamp.",
        )


async def require_conversation_and_timestamp_ok(
    *,
    api_context: ApiContext,
    connection: WebsocketConnection,
    conv_id: str,
    request_id: str,
    user_id: int,
    assistant_at_ms: int,
    before_timestamp_exclusive: int | None = None,
    counting_mode: Literal["canonical", "including_comparison_variants"] = "canonical",
    trace_id: str | None,
    logger: LoggerProtocol,
) -> ConversationStartSnapshot | None:
    result = await resolve_conversation_start_snapshot(
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
        assistant_at_ms=assistant_at_ms,
        before_timestamp_exclusive=before_timestamp_exclusive,
        counting_mode=counting_mode,
    )
    if isinstance(result, ConversationStartValidationFailure):
        if result.invalid_assistant_timestamp:
            await report_invalid_start_assistant_at_ms(
                connection=connection,
                conv_id=conv_id,
                request_id=request_id,
                logger=logger,
                trace_id=trace_id,
                exception=ValidationError(result.message),
            )
            return None
        await enqueue_chat_stream_start_error(
            connection,
            conv_id,
            request_id,
            result.code,
            result.message,
        )
        return None
    return result


async def resolve_conversation_start_snapshot(
    *,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    assistant_at_ms: int,
    before_timestamp_exclusive: int | None = None,
    counting_mode: Literal["canonical", "including_comparison_variants"] = "canonical",
) -> ConversationStartSnapshot | ConversationStartValidationFailure:
    database_messages = api_context.dependencies.webui_manager.database_messages
    resolved_before_timestamp_exclusive = before_timestamp_exclusive
    if resolved_before_timestamp_exclusive is None:
        raise ValidationError("before_timestamp_exclusive is required for chat stream start.")
    snapshot = await database_messages.get_conversation_start_snapshot(
        conv_id,
        user_id,
        before_timestamp_exclusive=int(resolved_before_timestamp_exclusive),
        counting_mode=counting_mode,
    )
    if snapshot is None:
        return ConversationStartValidationFailure(
            code="not_found_error",
            message="Conversation not found.",
            invalid_assistant_timestamp=False,
        )
    active_inputs = await api_context.dependencies.database_input_queue.summarize_active_inputs(
        conv_id=conv_id,
        user_id=user_id,
    )
    if active_inputs.has_active_inputs:
        return ConversationStartValidationFailure(
            code="conflict_error",
            message="Conversation stream start is unavailable while input work is active.",
            invalid_assistant_timestamp=False,
            snapshot=snapshot,
        )
    if await api_context.dependencies.database_stream_cancellations.has_pending(
        conv_id=conv_id,
        user_id=user_id,
    ):
        return ConversationStartValidationFailure(
            code="conflict_error",
            message="Conversation stream start is unavailable while cancellation is pending.",
            invalid_assistant_timestamp=False,
            snapshot=snapshot,
        )
    running_root_turn = await api_context.dependencies.database_agent_turns.get_running_root_turn(
        conv_id=conv_id,
        user_id=user_id,
    )
    if running_root_turn is not None:
        return ConversationStartValidationFailure(
            code="conflict_error",
            message="Conversation stream start is unavailable while an agent turn is running.",
            invalid_assistant_timestamp=False,
            snapshot=snapshot,
        )
    try:
        validate_assistant_at_ms(
            latest_message_timestamp=snapshot.latest_message_timestamp,
            assistant_at_ms=assistant_at_ms,
        )
    except ValidationError as exception:
        return ConversationStartValidationFailure(
            code="invalid_request_error",
            message=str(exception),
            invalid_assistant_timestamp=True,
            snapshot=snapshot,
        )

    return snapshot
