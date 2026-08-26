"""SoAI - OpenAI conversation request normalization [backend/core/openai/conversation_request_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from core.types.json_value import coerce_json_dict

__all__ = ("normalize_conv_id_and_messages_payload",)


def normalize_conv_id_and_messages_payload(payload: JSONDict) -> tuple[str | None, list[JSONDict]]:
    conv_id_value = payload.get("conv_id")
    if conv_id_value is None:
        return (None, [])
    if not isinstance(conv_id_value, str):
        raise ValidationError("conv_id must be a string.", details={"param": "conv_id"})
    normalized_conv_id = conv_id_value.strip()
    if not normalized_conv_id:
        raise ValidationError(
            "conv_id must be a non-empty string.",
            details={"param": "conv_id"},
        )
    raw_messages = payload.get("messages", [])
    if not isinstance(raw_messages, list):
        raise ValidationError("messages must be a list.", details={"param": "messages"})
    messages: list[JSONDict] = []
    for index, item in enumerate(raw_messages):
        message = coerce_json_dict(item)
        if message is None:
            raise ValidationError(
                "messages must contain JSON objects.",
                details={"param": f"messages[{index}]"},
            )
        messages.append(message)
    payload["messages"] = messages
    return (normalized_conv_id, messages)
