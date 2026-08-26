"""SoAI - Compaction content projection [backend/features/api/routes/openai/compaction/content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.truncation import build_prefix_truncation_text
from core.serialization.json import serialize_json_compact_stable
from core.types.json_value import coerce_json_dict, filter_json_dict_list

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "coerce_content_to_text",
    "project_message_for_summary",
)

_MAX_TOOL_CALLS_PREVIEW_CHARS: int = 2000


def coerce_content_to_text(content: JSONValue) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return serialize_json_compact_stable(content, ensure_ascii=False)


def _extract_tool_call_name(tool_call: JSONDict) -> str:
    name_value = tool_call.get("name")
    name = name_value.strip() if isinstance(name_value, str) else ""
    if name:
        return name
    function_value = tool_call.get("function")
    function = coerce_json_dict(function_value)
    if function is not None:
        function_name_value = function.get("name")
        function_name = function_name_value.strip() if isinstance(function_name_value, str) else ""
        if function_name:
            return function_name
    return "unknown"


def _build_tool_calls_preview(tool_calls: list[JSONDict]) -> str | None:
    if not tool_calls:
        return None
    preview_entries: list[JSONDict] = []
    for tool_call in tool_calls[:20]:
        entry: JSONDict = {"name": _extract_tool_call_name(tool_call)}
        arguments_value = tool_call.get("arguments")
        if isinstance(arguments_value, str) and arguments_value:
            entry["arguments_preview"] = (
                arguments_value
                if len(arguments_value) <= 400
                else build_prefix_truncation_text(original=arguments_value, prefix_length=400)
            )
        function = coerce_json_dict(tool_call.get("function"))
        if function is not None:
            function_arguments_value = function.get("arguments")
            if isinstance(function_arguments_value, str) and function_arguments_value:
                entry["arguments_preview"] = (
                    function_arguments_value
                    if len(function_arguments_value) <= 400
                    else build_prefix_truncation_text(
                        original=function_arguments_value,
                        prefix_length=400,
                    )
                )
        preview_entries.append(entry)
    if not preview_entries:
        return None
    serialized = serialize_json_compact_stable(preview_entries, ensure_ascii=False)
    if len(serialized) <= _MAX_TOOL_CALLS_PREVIEW_CHARS:
        return serialized
    return build_prefix_truncation_text(
        original=serialized,
        prefix_length=_MAX_TOOL_CALLS_PREVIEW_CHARS,
    )


def project_message_for_summary(message: JSONDict) -> JSONDict:
    role_value = message.get("role")
    role = role_value.strip() if isinstance(role_value, str) else ""
    content_text = coerce_content_to_text(message.get("content"))
    if role == "assistant":
        tool_calls_value = message.get("tool_calls")
        tool_calls_preview = _build_tool_calls_preview(filter_json_dict_list(tool_calls_value))
        if tool_calls_preview is not None:
            content_text = (
                f"{content_text}\n\n<tool_calls_preview_json>\n"
                f"{tool_calls_preview}\n</tool_calls_preview_json>"
            )
    if role == "tool":
        tool_call_id_value = message.get("tool_call_id")
        tool_call_id = tool_call_id_value.strip() if isinstance(tool_call_id_value, str) else ""
        if tool_call_id:
            content_text = f"<tool_call_id>{tool_call_id}</tool_call_id>\n{content_text}"
    return {"role": role or "user", "content": content_text}
