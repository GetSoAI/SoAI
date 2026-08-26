"""SoAI - Tool-call dialogue conversion for strict chat templates [backend/core/openai/tool_dialogue_conversion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterable

from core.openai.message_sequence_normalization import (
    coerce_openai_message_content_to_text,
    merge_adjacent_dialogue_turns_for_strict_templates,
    merge_text_fragments,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict, JSONValue
from core.types.json_value import require_json_dict

__all__ = ("convert_tool_messages_to_user_assistant_turns_for_strict_templates",)


def _render_tool_call(tool_call: JSONDict) -> str:
    tool_call_id_value = tool_call.get("id")
    tool_call_id = tool_call_id_value.strip() if isinstance(tool_call_id_value, str) else ""
    function_value = tool_call.get("function")
    name_value: JSONValue = None
    arguments_value: JSONValue = None
    if isinstance(function_value, dict):
        name_value = function_value.get("name")
        arguments_value = function_value.get("arguments")
    name = name_value.strip() if isinstance(name_value, str) else ""
    arguments = coerce_openai_message_content_to_text(arguments_value)
    fragments: list[str] = []
    if name:
        fragments.append(f"name: {name}")
    if tool_call_id:
        fragments.append(f"id: {tool_call_id}")
    if arguments:
        fragments.append(f"arguments: {arguments}")
    if fragments:
        return "\n".join(fragments)
    return serialize_json_compact_stable_strict(tool_call, ensure_ascii=False)


def _render_tool_calls(tool_calls: JSONValue) -> str:
    if not isinstance(tool_calls, list):
        return ""
    rendered: list[str] = []
    for index, entry in enumerate(tool_calls, start=1):
        if not isinstance(entry, dict):
            continue
        tool_call = _render_tool_call(entry)
        if tool_call:
            rendered.append(f"Tool call {index}:\n{tool_call}")
    if not rendered:
        return ""
    rendered_text = "\n\n".join(rendered)
    return f"Assistant requested tool calls:\n{rendered_text}"


def _convert_assistant_tool_calls(message: JSONDict) -> JSONDict:
    converted = dict(message)
    tool_calls = converted.pop("tool_calls", None)
    rendered_tool_calls = _render_tool_calls(tool_calls)
    if not rendered_tool_calls:
        return converted
    converted["content"] = merge_text_fragments(
        coerce_openai_message_content_to_text(converted.get("content")),
        rendered_tool_calls,
    )
    return converted


def _convert_tool_result(message: JSONDict) -> JSONDict:
    tool_call_id_value = message.get("tool_call_id")
    tool_call_id = tool_call_id_value.strip() if isinstance(tool_call_id_value, str) else ""
    name_value = message.get("name")
    name = name_value.strip() if isinstance(name_value, str) else ""
    heading_fragments: list[str] = ["Tool result"]
    if name:
        heading_fragments.append(f"name: {name}")
    if tool_call_id:
        heading_fragments.append(f"id: {tool_call_id}")
    content_text = coerce_openai_message_content_to_text(message.get("content"))
    return {
        "role": "user",
        "content": merge_text_fragments("\n".join(heading_fragments), content_text),
    }


def convert_tool_messages_to_user_assistant_turns_for_strict_templates(
    messages: Iterable[JSONDict],
) -> list[JSONDict]:
    converted_messages: list[JSONDict] = []
    for index, raw in enumerate(messages):
        message = require_json_dict(raw, label=f"messages[{index}]")
        role_value = message.get("role")
        role = role_value.strip() if isinstance(role_value, str) else ""
        if role == "assistant":
            converted_messages.append(_convert_assistant_tool_calls(message))
            continue
        if role == "tool":
            converted_messages.append(_convert_tool_result(message))
            continue
        converted_messages.append(message)
    return merge_adjacent_dialogue_turns_for_strict_templates(converted_messages)
