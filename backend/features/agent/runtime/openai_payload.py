"""SoAI - Agent OpenAI payload parsing [backend/features/agent/runtime/openai_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.openai.content_text_coercion import coerce_openai_content_text
from core.openai.stream_transcript.text_classifier import OpenAIStreamTextClassifier
from core.openai.usage.resolution import normalize_provider_usage
from features.agent.runtime.turn_iteration_policy_types import (
    FINISH_REASON_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION,
    FINISH_REASON_TOOL_CALL_PROTOCOL_VIOLATION,
)

if TYPE_CHECKING:
    from core.openai.usage.models import CanonicalUsage
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "coerce_usage_dict",
    "complete_assistant_tool_calls_as_stopped",
    "extract_assistant_content_raw",
    "extract_assistant_content_visible",
    "extract_finish_reason",
    "extract_usage",
    "remove_length_truncated_assistant_tool_calls",
    "remove_rejected_assistant_tool_calls",
    "remove_suppressed_assistant_tool_calls",
    "replace_assistant_content_visible",
    "resolve_payload_model",
)


def extract_assistant_content_raw(payload: JSONDict) -> str:
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list):
        return ""
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        text_value = choice.get("text")
        if isinstance(text_value, str) and text_value:
            return text_value
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if content is None:
            continue
        coerced = coerce_openai_content_text(content)
        if coerced:
            return coerced
    return ""


def extract_assistant_content_visible(payload: JSONDict) -> str:
    classifier = OpenAIStreamTextClassifier()
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list):
        return ""
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message_value = choice.get("message")
        message = message_value if isinstance(message_value, dict) else None
        if message is not None:
            classifier.consume_text_source(message)
            continue
        text_value = choice.get("text")
        if isinstance(text_value, str) and text_value:
            classifier.consume_content_text(text_value)
    classifier.finalize()
    return classifier.get_visible_text()


def replace_assistant_content_visible(payload: JSONDict, assistant_text: str) -> None:
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list):
        return
    normalized_text = assistant_text
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message_value = choice.get("message")
        if isinstance(message_value, dict):
            message_value["content"] = normalized_text
            if "parts" in message_value:
                message_value.pop("parts", None)
            return
        if "text" in choice:
            choice["text"] = normalized_text
            return


def _remove_assistant_tool_calls(payload: JSONDict, *, finish_reason: str) -> bool:
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list):
        return False
    removed = False
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message_value = choice.get("message")
        if not isinstance(message_value, dict):
            continue
        if "tool_calls" not in message_value:
            continue
        message_value.pop("tool_calls", None)
        choice["finish_reason"] = finish_reason
        removed = True
    return removed


def remove_suppressed_assistant_tool_calls(
    payload: JSONDict,
    *,
    assistant_text: str,
) -> bool:
    finish_reason = (
        "stop"
        if assistant_text.strip()
        else FINISH_REASON_INVALID_TOOL_CALL_JSON_CONTRACT_VIOLATION
    )
    return _remove_assistant_tool_calls(payload, finish_reason=finish_reason)


def remove_rejected_assistant_tool_calls(payload: JSONDict) -> bool:
    return _remove_assistant_tool_calls(
        payload,
        finish_reason=FINISH_REASON_TOOL_CALL_PROTOCOL_VIOLATION,
    )


def remove_length_truncated_assistant_tool_calls(payload: JSONDict) -> bool:
    return _remove_assistant_tool_calls(payload, finish_reason="length")


def complete_assistant_tool_calls_as_stopped(
    payload: JSONDict,
    *,
    assistant_text: str | None,
) -> bool:
    normalized_text = assistant_text or ""
    replace_assistant_content_visible(payload, normalized_text)
    return _remove_assistant_tool_calls(payload, finish_reason="stop")


def resolve_payload_model(payload: JSONDict) -> str | None:
    value = payload.get("model")
    return value if isinstance(value, str) and value.strip() else None


def extract_finish_reason(payload: JSONDict) -> str | None:
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if not isinstance(choices, list):
        return None
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        finish_reason = choice.get("finish_reason")
        if isinstance(finish_reason, str) and finish_reason.strip():
            return finish_reason
    return None


def coerce_usage_dict(usage: Mapping[str, JSONValue] | None) -> CanonicalUsage | None:
    if not isinstance(usage, Mapping):
        return None
    normalized = normalize_provider_usage(usage_payload=dict(usage), prompt_tokens_hint=None)
    return normalized.usage


def extract_usage(payload: JSONDict) -> CanonicalUsage | None:
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, Mapping):
        return None
    return coerce_usage_dict(usage)
