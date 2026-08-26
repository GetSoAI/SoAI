"""SoAI - OpenAI request message extraction [backend/features/agent/runtime/request_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.content_text_coercion import coerce_openai_content_text
from core.openai.internal_message_metadata import SOAI_MESSAGE_TYPE_FIELD
from core.tool_calls.context_compaction_markers import (
    CONTEXT_COMPACTION_POST_ASSISTANT_TEXT_FIELD,
)
from core.types.json import is_json_value
from core.types.json_value import coerce_json_dict, copy_json_value

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "extract_openai_messages",
    "should_include_message_in_agent_prompt",
    "strip_internal_message_metadata",
)

_INTERNAL_MESSAGE_FIELDS: frozenset[str] = frozenset(
    (
        "timestamp",
        "id",
        "assistant_turn_at_ms",
        "model_variant_index",
        "model_id",
        "request_id",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "generation_latency_ms",
        "finish_reason",
        "thinking_tail_duration_ms",
        "generation_speed_tokens_per_sec",
        "assistant_event_timeline",
        "tool_call_projections",
        "error_code",
        "usage",
        "attachments",
        "images",
        "documents",
        "message",
        "inline_thinking_collapsed_by_call_id",
        "inline_tool_collapsed_by_call_id",
        SOAI_MESSAGE_TYPE_FIELD,
        "soai_compaction",
        CONTEXT_COMPACTION_POST_ASSISTANT_TEXT_FIELD,
    ),
)


def should_include_message_in_agent_prompt(message: JSONDict) -> bool:
    if message.get("role") != "assistant":
        return True
    finish_reason = message.get("finish_reason")
    if not isinstance(finish_reason, str) or finish_reason != "error":
        return True
    return bool(coerce_openai_content_text(message.get("content")).strip())


def extract_openai_messages(request_json: JSONDict) -> list[JSONDict]:
    messages_value = request_json.get("messages")
    messages: list[JSONDict] = []
    if not isinstance(messages_value, list):
        return messages
    for item in messages_value:
        if not isinstance(item, dict):
            continue
        if not is_json_value(item):
            continue
        message = coerce_json_dict(item)
        if message is not None and should_include_message_in_agent_prompt(message):
            messages.append(message)
    return messages


def strip_internal_message_metadata(messages: list[JSONDict]) -> list[JSONDict]:
    sanitized_messages: list[JSONDict] = []
    for message in messages:
        sanitized_message: JSONDict = {}
        for field_name, value in message.items():
            if field_name in _INTERNAL_MESSAGE_FIELDS:
                continue
            sanitized_message[field_name] = copy_json_value(value)
        sanitized_messages.append(sanitized_message)
    return sanitized_messages
