"""SoAI - Durable conversation outbox event decoding [backend/app/background/domain_event_outbox_conversation_decoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.background.outbox_payload_parsing import (
    coerce_outbox_bool,
    coerce_outbox_int,
    coerce_outbox_str,
)
from core.errors.exceptions import ValidationError
from core.events.types_conversation import ConversationUpdatedEvent
from core.events.types_conversation_durable import (
    ConversationAttentionChangedEvent,
    ConversationControlCompletedEvent,
    ConversationInputTerminalEvent,
    ConversationInteractionRequiredEvent,
    ConversationStreamCancellationRequestedEvent,
    ConversationStreamCancellationSettledEvent,
)
from core.openai.model_settings_validation import validate_model_settings

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("decode_conversation_outbox_event",)


def decode_conversation_outbox_event(
    *,
    decoded: dict[str, JSONValue],
    event_type: str,
    event_id: str,
    timestamp: float,
) -> (
    ConversationControlCompletedEvent
    | ConversationAttentionChangedEvent
    | ConversationInputTerminalEvent
    | ConversationInteractionRequiredEvent
    | ConversationStreamCancellationRequestedEvent
    | ConversationStreamCancellationSettledEvent
    | ConversationUpdatedEvent
):
    if event_type == "ConversationStreamCancellationSettledEvent":
        return ConversationStreamCancellationSettledEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=coerce_outbox_int(decoded.get("user_id"), label="user_id"),
            conv_id=coerce_outbox_str(
                decoded.get("conversation_id"),
                label="conversation_id",
            ),
            request_id=coerce_outbox_str(decoded.get("request_id"), label="request_id"),
        )
    if event_type == "ConversationStreamCancellationRequestedEvent":
        return ConversationStreamCancellationRequestedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=coerce_outbox_int(decoded.get("user_id"), label="user_id"),
            conv_id=coerce_outbox_str(
                decoded.get("conversation_id"),
                label="conversation_id",
            ),
            request_id=coerce_outbox_str(decoded.get("request_id"), label="request_id"),
            force_pending_steers=coerce_outbox_bool(
                decoded.get("force_pending_steers"),
                label="force_pending_steers",
            ),
        )
    if event_type == "ConversationUpdatedEvent":
        last_modified_at_ms = coerce_outbox_int(
            decoded.get("last_modified_at_ms"),
            label="last_modified_at_ms",
        )
        if last_modified_at_ms <= 0:
            raise ValidationError("last_modified_at_ms must be positive.")
        model_settings = decoded.get("model_settings")
        if not isinstance(model_settings, dict):
            raise ValidationError("model_settings must be an object.")
        return ConversationUpdatedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=coerce_outbox_int(decoded.get("user_id"), label="user_id"),
            conv_id=coerce_outbox_str(decoded.get("conv_id"), label="conv_id"),
            last_modified_at_ms=last_modified_at_ms,
            model_settings=validate_model_settings(model_settings),
        )
    if event_type == "ConversationAttentionChangedEvent":
        conv_id_value = decoded.get("conv_id")
        if conv_id_value is not None and not isinstance(conv_id_value, str):
            raise ValidationError("conv_id must be a string or null.")
        return ConversationAttentionChangedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=coerce_outbox_int(decoded.get("user_id"), label="user_id"),
            conv_id=conv_id_value,
        )
    if event_type == "ConversationControlCompletedEvent":
        source_message_id = coerce_outbox_int(
            decoded.get("source_message_id"),
            label="source_message_id",
        )
        if source_message_id <= 0:
            raise ValidationError("source_message_id must be positive.")
        return ConversationControlCompletedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=coerce_outbox_int(decoded.get("user_id"), label="user_id"),
            conv_id=coerce_outbox_str(decoded.get("conv_id"), label="conv_id"),
            target_conv_id=coerce_outbox_str(
                decoded.get("target_conv_id"),
                label="target_conv_id",
            ),
            control_id=coerce_outbox_str(decoded.get("control_id"), label="control_id"),
            source_message_id=source_message_id,
        )
    if event_type == "ConversationInteractionRequiredEvent":
        return ConversationInteractionRequiredEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=coerce_outbox_int(decoded.get("user_id"), label="user_id"),
            conv_id=coerce_outbox_str(decoded.get("conv_id"), label="conv_id"),
            input_id=coerce_outbox_str(decoded.get("input_id"), label="input_id"),
            task_id=coerce_outbox_str(decoded.get("task_id"), label="task_id"),
            route_id=coerce_outbox_str(decoded.get("route_id"), label="route_id"),
            interaction_type=coerce_outbox_str(
                decoded.get("interaction_type"),
                label="interaction_type",
            ),
            reply_token=coerce_outbox_str(decoded.get("reply_token"), label="reply_token"),
            focus_nonce=coerce_outbox_str(decoded.get("focus_nonce"), label="focus_nonce"),
        )
    if event_type != "ConversationInputTerminalEvent":
        raise ValidationError(f"Unsupported conversation outbox event_type: {event_type}")
    source_message_value = decoded.get("source_message_id")
    optional_source_message_id = (
        None
        if source_message_value is None
        else coerce_outbox_int(source_message_value, label="source_message_id")
    )
    if optional_source_message_id is not None and optional_source_message_id <= 0:
        raise ValidationError("source_message_id must be positive when present.")
    return ConversationInputTerminalEvent(
        event_id=event_id,
        timestamp=timestamp,
        user_id=coerce_outbox_int(decoded.get("user_id"), label="user_id"),
        conv_id=coerce_outbox_str(decoded.get("conv_id"), label="conv_id"),
        input_id=coerce_outbox_str(decoded.get("input_id"), label="input_id"),
        source_message_id=optional_source_message_id,
        terminal_state=coerce_outbox_str(
            decoded.get("terminal_state"),
            label="terminal_state",
        ),
        terminal_code=coerce_outbox_str(
            decoded.get("terminal_code"),
            label="terminal_code",
        ),
    )
