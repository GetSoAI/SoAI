"""SoAI - Prompt history tool-result shaping [backend/core/tool_calls/tool_result_prompt_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.serialization.json_parsing import parse_json_value
from core.tool_calls.tool_result_prompt_settings import (
    DEFAULT_TOOL_RESULT_PROMPT_MAX_CHARS,
    DEFAULT_TOOL_RESULT_PROMPT_MAX_DEPTH,
    DEFAULT_TOOL_RESULT_PROMPT_MAX_ITEMS,
    DEFAULT_TOOL_RESULT_PROMPT_MAX_KEYS,
)
from core.types.json_value import coerce_json_dict

if TYPE_CHECKING:
    from core.tool_calls.tool_result_prompt_cache import ToolResultPromptShapeCache
    from core.types.json import JSONDict

__all__ = ("shape_prompt_history_tool_results",)


def _resolve_assistant_tool_names(message: JSONDict) -> dict[str, str]:
    tool_calls_value = message.get("tool_calls")
    if not isinstance(tool_calls_value, list):
        return {}
    tool_names_by_id: dict[str, str] = {}
    for tool_call_value in tool_calls_value:
        tool_call = coerce_json_dict(tool_call_value)
        if tool_call is None:
            continue
        call_id_value = tool_call.get("id")
        call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
        function_value = coerce_json_dict(tool_call.get("function"))
        if not call_id or function_value is None:
            continue
        name_value = function_value.get("name")
        name = name_value.strip() if isinstance(name_value, str) else ""
        if name:
            tool_names_by_id[call_id] = name
    return tool_names_by_id


def _resolve_tool_name(message: JSONDict, tool_names_by_id: dict[str, str]) -> str:
    call_id_value = message.get("tool_call_id")
    call_id = call_id_value.strip() if isinstance(call_id_value, str) else ""
    name = tool_names_by_id.get(call_id)
    return name if name is not None else "unknown"


def _shape_tool_message(
    message: JSONDict,
    tool_names_by_id: dict[str, str],
    shape_cache: ToolResultPromptShapeCache,
) -> JSONDict:
    content_value = message.get("content")
    if not isinstance(content_value, str) or not content_value.strip():
        return dict(message)
    normalized_content = content_value.strip()
    if not normalized_content.startswith("{"):
        return dict(message)
    parsed = parse_json_value(normalized_content, field="tool result prompt content")
    result = coerce_json_dict(parsed)
    if result is None:
        return dict(message)
    tool_name = _resolve_tool_name(message, tool_names_by_id)
    shaped_json = shape_cache.shape(
        tool_name=tool_name,
        tool_result=result,
        max_chars=DEFAULT_TOOL_RESULT_PROMPT_MAX_CHARS,
        max_depth=DEFAULT_TOOL_RESULT_PROMPT_MAX_DEPTH,
        max_items=DEFAULT_TOOL_RESULT_PROMPT_MAX_ITEMS,
        max_keys=DEFAULT_TOOL_RESULT_PROMPT_MAX_KEYS,
    )
    shaped_message = dict(message)
    shaped_message["content"] = shaped_json
    return shaped_message


def shape_prompt_history_tool_results(
    messages: Sequence[JSONDict],
    *,
    shape_cache: ToolResultPromptShapeCache,
) -> list[JSONDict]:
    shaped_messages: list[JSONDict] = []
    tool_names_by_id: dict[str, str] = {}
    for message in messages:
        if message.get("role") == "assistant":
            tool_names_by_id.update(_resolve_assistant_tool_names(message))
            shaped_messages.append(dict(message))
            continue
        if message.get("role") == "tool":
            shaped_messages.append(_shape_tool_message(message, tool_names_by_id, shape_cache))
            continue
        shaped_messages.append(dict(message))
    return shaped_messages
