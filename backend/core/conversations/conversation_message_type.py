"""SoAI - Canonical conversation message type contract [backend/core/conversations/conversation_message_type.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.types.json import JSONValue

__all__ = ("require_conversation_message_type",)

if TYPE_CHECKING:
    from typing import Literal

    type ConversationMessageType = Literal["chat", "control"]


def require_conversation_message_type(value: JSONValue | None) -> ConversationMessageType:
    if value is not None and not isinstance(value, str):
        raise ValidationError("Conversation message type must be a string.")
    normalized = "chat" if value is None else value.strip()
    if normalized == "chat":
        return "chat"
    if normalized == "control":
        return "control"
    raise ValidationError("Conversation message type must be chat or control.")
