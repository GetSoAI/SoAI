"""SoAI - OpenAI message sequence normalization for strict chat templates [backend/core/openai/message_sequence_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable

from core.errors.exceptions import ValidationError
from core.openai.chat_messages_contracts import extract_expected_tool_call_ids
from core.openai.content_text_coercion import coerce_openai_content_text
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict, JSONValue
from core.types.json_value import require_json_dict

__all__ = (
    "coerce_openai_message_content_to_text",
    "merge_adjacent_dialogue_turns_for_strict_templates",
    "merge_text_fragments",
    "prefix_user_message_with_text",
)

_DIALOGUE_ROLES: frozenset[str] = frozenset(("user", "assistant"))


def _coerce_text(value: JSONValue) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        parts: list[str] = []
        for entry in value:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "text":
                continue
            text_value = entry.get("text")
            if isinstance(text_value, str) and text_value:
                parts.append(text_value)
        return "\n".join(parts)
    text_value = coerce_openai_content_text(value)
    if text_value:
        return text_value
    return serialize_json_compact_stable_strict(value, ensure_ascii=False)


def _merge_text(left: str, right: str) -> str:
    left_text = str(left or "").strip()
    right_text = str(right or "").strip()
    if not left_text:
        return right_text
    if not right_text:
        return left_text
    return f"{left_text}\n\n{right_text}"


def _merge_content(left: JSONValue, right: JSONValue) -> JSONValue:
    return _merge_text(_coerce_text(left), _coerce_text(right))


def _merge_tool_calls(left: JSONValue, right: JSONValue) -> list[JSONDict] | None:
    left_list = left if isinstance(left, list) else None
    right_list = right if isinstance(right, list) else None
    if not left_list and not right_list:
        return None
    merged: list[JSONDict] = []
    if left_list:
        for entry in left_list:
            if isinstance(entry, dict):
                merged.append(dict(entry))
    if right_list:
        for entry in right_list:
            if isinstance(entry, dict):
                merged.append(dict(entry))
    return merged


def merge_adjacent_dialogue_turns_for_strict_templates(
    messages: Iterable[JSONDict],
) -> list[JSONDict]:
    normalized: list[JSONDict] = []
    last_role: str | None = None
    tool_call_ids_expected: tuple[str, ...] | None = None
    tool_call_ids_satisfied: set[str] = set()
    tool_call_source_index: int | None = None

    for index, raw in enumerate(messages):
        message = require_json_dict(raw, label=f"messages[{index}]")
        role_value = message.get("role")
        role = role_value.strip() if isinstance(role_value, str) else ""
        if not role:
            raise ValidationError(
                "Message role is required.",
                details={"param": f"messages[{index}].role"},
            )
        if role == "tool":
            expected_tool_call_ids = tool_call_ids_expected
            if expected_tool_call_ids is None:
                raise ValidationError(
                    "Tool message without a preceding assistant tool_calls message.",
                    details={"param": f"messages[{index}].role"},
                )
            tool_call_id_value = message.get("tool_call_id")
            tool_call_id = tool_call_id_value.strip() if isinstance(tool_call_id_value, str) else ""
            if not tool_call_id:
                raise ValidationError(
                    "tool_call_id is required for tool messages.",
                    details={"param": f"messages[{index}].tool_call_id"},
                )
            tool_call_ids = tuple(expected_tool_call_ids)
            if tool_call_id not in tool_call_ids:
                source_index = tool_call_source_index if tool_call_source_index is not None else 0
                raise ValidationError(
                    "tool_call_id does not match any active tool call.",
                    details={
                        "param": f"messages[{index}].tool_call_id",
                        "source": f"messages[{source_index}].tool_calls",
                    },
                )
            if tool_call_id in tool_call_ids_satisfied:
                raise ValidationError(
                    "Duplicate tool result for tool_call_id.",
                    details={"param": f"messages[{index}].tool_call_id"},
                )
            tool_call_ids_satisfied.add(tool_call_id)
            normalized.append(message)
            if len(tool_call_ids_satisfied) == len(expected_tool_call_ids):
                tool_call_ids_expected = None
                tool_call_ids_satisfied = set()
                tool_call_source_index = None
            last_role = "tool"
            continue
        if tool_call_ids_expected is not None:
            raise ValidationError(
                "Non-tool message encountered before all tool results were provided.",
                details={"param": f"messages[{index}].role"},
            )
        if role in _DIALOGUE_ROLES:
            if normalized and last_role == role and normalized[-1].get("role") == role:
                previous = dict(normalized[-1])
                previous["content"] = _merge_content(
                    previous.get("content"),
                    message.get("content"),
                )
                if role == "assistant":
                    merged_tool_calls = _merge_tool_calls(
                        previous.get("tool_calls"),
                        message.get("tool_calls"),
                    )
                    if merged_tool_calls is not None:
                        previous["tool_calls"] = merged_tool_calls
                normalized[-1] = previous
            else:
                normalized.append(message)
                last_role = role
            if role == "assistant":
                expected = extract_expected_tool_call_ids(
                    message.get("tool_calls"),
                    message_index=index,
                )
                if expected:
                    tool_call_ids_expected = expected
                    tool_call_source_index = index
                    tool_call_ids_satisfied = set()
            continue
        normalized.append(message)
        last_role = role
    if tool_call_ids_expected is not None:
        raise ValidationError(
            "Missing tool results for tool_calls.",
            details={"param": "messages"},
        )
    return normalized


def prefix_user_message_with_text(user_message: JSONDict, prefix_text: str) -> JSONDict:
    prefix = str(prefix_text or "").strip()
    if not prefix:
        return dict(user_message)
    message = dict(user_message)
    content = message.get("content")
    if isinstance(content, str):
        message["content"] = _merge_text(prefix, content)
        return message
    if isinstance(content, list):
        new_parts: list[JSONDict] = [{"type": "text", "text": prefix}]
        for part in content:
            if isinstance(part, dict):
                new_parts.append(dict(part))
        message["content"] = new_parts
        return message
    message["content"] = prefix
    return message


def coerce_openai_message_content_to_text(value: JSONValue) -> str:
    return _coerce_text(value)


def merge_text_fragments(left: str, right: str) -> str:
    return _merge_text(left, right)
