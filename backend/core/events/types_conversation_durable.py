"""SoAI - Durable canonical conversation event types [backend/core/events/types_conversation_durable.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.events.types_base import Event

__all__ = (
    "ConversationControlCompletedEvent",
    "ConversationAttentionChangedEvent",
    "ConversationInputTerminalEvent",
    "ConversationInteractionRequiredEvent",
    "ConversationStreamCancellationRequestedEvent",
    "ConversationStreamCancellationSettledEvent",
)


@dataclass(slots=True)
class ConversationAttentionChangedEvent(Event):
    user_id: int
    conv_id: str | None


@dataclass(slots=True)
class ConversationControlCompletedEvent(Event):
    user_id: int
    conv_id: str
    target_conv_id: str
    control_id: str
    source_message_id: int


@dataclass(slots=True)
class ConversationInputTerminalEvent(Event):
    user_id: int
    conv_id: str
    input_id: str
    source_message_id: int | None
    terminal_state: str
    terminal_code: str


@dataclass(slots=True)
class ConversationStreamCancellationRequestedEvent(Event):
    user_id: int
    conv_id: str
    request_id: str
    force_pending_steers: bool


@dataclass(slots=True)
class ConversationStreamCancellationSettledEvent(Event):
    user_id: int
    conv_id: str
    request_id: str


@dataclass(slots=True)
class ConversationInteractionRequiredEvent(Event):
    user_id: int
    conv_id: str
    input_id: str
    task_id: str
    route_id: str
    interaction_type: str
    reply_token: str
    focus_nonce: str
