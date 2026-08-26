"""SoAI - Shared context compaction prompt-message contract [backend/core/tool_calls/context_compaction_prompt_message.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.serialization.json import normalize_for_json
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "extract_context_compaction_prompt_message_from_result_payload",
    "normalize_context_compaction_prompt_message",
)

_PROMPT_MESSAGE_FIELD = "prompt_message"


def normalize_context_compaction_prompt_message(value: JSONValue) -> JSONDict | None:
    message = coerce_json_dict(normalize_for_json(value))
    if message is None:
        return None
    role_value = message.get("role")
    role = role_value.strip() if isinstance(role_value, str) else ""
    content_value = message.get("content")
    if not role or not isinstance(content_value, str) or content_value == "":
        return None
    normalized: JSONDict = {
        "role": role,
        "content": content_value,
    }
    name_value = message.get("name")
    name = name_value.strip() if isinstance(name_value, str) else ""
    if name:
        normalized["name"] = name
    return normalized


def extract_context_compaction_prompt_message_from_result_payload(
    result_payload: Mapping[str, JSONValue],
) -> JSONDict | None:
    return normalize_context_compaction_prompt_message(result_payload.get(_PROMPT_MESSAGE_FIELD))
