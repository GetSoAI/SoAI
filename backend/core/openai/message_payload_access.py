"""SoAI - OpenAI message payload access and structural validation [backend/core/openai/message_payload_access.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_openai_payload_message_dicts",)


def get_openai_payload_message_dicts(
    payload: JSONDict,
    *,
    trace_id: str | None = None,
) -> list[JSONDict] | None:
    messages_value = payload.get("messages")
    if messages_value is None:
        return None
    if not isinstance(messages_value, list):
        raise ValidationError(
            "Messages must be an array.",
            details={"param": "messages"},
            trace_id=trace_id,
        )
    messages: list[JSONDict] = []
    for index, message in enumerate(messages_value):
        if not isinstance(message, dict):
            raise ValidationError(
                f"Message at index {index} must be an object.",
                details={"param": f"messages[{index}]"},
                trace_id=trace_id,
            )
        messages.append(message)
    return messages
