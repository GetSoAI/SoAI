"""SoAI - Agent context compaction message rewrite helpers [backend/features/agent/runtime/context_compaction/rewrite.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.openai.content_text_rendering import render_openai_content_text
from core.serialization.json import (
    serialize_json_compact_stable_strict,
    try_serialize_json_compact_stable_default_str,
)
from core.serialization.json_parsing import parse_json_value
from core.types.json import JSONDict, JSONValue
from features.agent.runtime.tool_call_arguments_compaction import (
    compact_tool_call_arguments,
)

__all__ = ("rewrite_history_for_compaction",)

_TOOL_STUB_MARKER_KEY: str = "__soai_compaction__"
_TOOL_STUB_REASON: str = "tool_result_compacted"


def _compact_tool_call_arguments_value(value: JSONValue) -> str | None:
    if isinstance(value, str):
        return compact_tool_call_arguments(value)
    if isinstance(value, dict | list):
        serialized = try_serialize_json_compact_stable_default_str(value, ensure_ascii=False)
        if isinstance(serialized, str) and serialized.strip():
            return compact_tool_call_arguments(serialized)
        return "{}"
    return None


def rewrite_assistant_tool_calls(message: JSONDict) -> JSONDict:
    tool_calls_value = message.get("tool_calls")
    if not isinstance(tool_calls_value, list):
        return message
    rewritten_tool_calls: list[JSONDict] = []
    for tool_call in tool_calls_value:
        if not isinstance(tool_call, dict):
            continue
        rewritten = dict(tool_call)
        raw_arguments = tool_call.get("arguments")
        compacted_raw = _compact_tool_call_arguments_value(raw_arguments)
        if compacted_raw is not None:
            rewritten["arguments"] = compacted_raw
        function_value = tool_call.get("function")
        if isinstance(function_value, dict):
            function_payload = dict(function_value)
            arguments_value = function_value.get("arguments")
            compacted_function = _compact_tool_call_arguments_value(arguments_value)
            if compacted_function is not None:
                function_payload["arguments"] = compacted_function
            rewritten["function"] = function_payload
        rewritten_tool_calls.append(rewritten)
    rewritten_message = dict(message)
    rewritten_message["tool_calls"] = rewritten_tool_calls
    return rewritten_message


def compact_code_diffs(value: JSONValue) -> list[JSONDict] | None:
    if not isinstance(value, list):
        return None
    compacted: list[JSONDict] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        path_value = entry.get("path")
        operation_value = entry.get("operation")
        diff_value = entry.get("diff")
        payload: JSONDict = {}
        if isinstance(path_value, str) and path_value.strip():
            payload["path"] = path_value.strip()
        if isinstance(operation_value, str) and operation_value.strip():
            payload["operation"] = operation_value.strip()
        if isinstance(diff_value, str) and diff_value:
            preview = diff_value[:800]
            payload["diff_preview"] = preview
            payload["truncated"] = len(diff_value) > len(preview)
        if payload:
            compacted.append(payload)
    return compacted or None


def build_tool_result_stub(*, content_text: str) -> JSONDict:
    preview = content_text[:1000]
    stub: JSONDict = {
        _TOOL_STUB_MARKER_KEY: {
            "truncated": len(content_text) > len(preview),
            "reason": _TOOL_STUB_REASON,
            "original_chars": len(content_text),
        },
        "preview": preview,
    }
    try:
        parsed = parse_json_value(content_text) if content_text.strip() else None
    except ValidationError:
        parsed = None
    if isinstance(parsed, dict):
        error_value = parsed.get("error")
        if isinstance(error_value, str) and error_value.strip():
            stub["error"] = error_value.strip()
        code_diffs = compact_code_diffs(parsed.get("code_diffs"))
        if code_diffs is not None:
            stub["code_diffs"] = code_diffs
        keys = [key for key in parsed if isinstance(key, str)]
        if keys:
            stub["summary_keys"] = sorted(keys)[:50]
    return stub


def rewrite_tool_message(message: JSONDict) -> JSONDict:
    if message.get("role") != "tool":
        return message
    content_text = render_openai_content_text(message.get("content"))
    stub = build_tool_result_stub(content_text=content_text)
    rewritten = dict(message)
    rewritten["content"] = serialize_json_compact_stable_strict(stub, ensure_ascii=False)
    return rewritten


def rewrite_history_for_compaction(message_history: list[JSONDict]) -> list[JSONDict]:
    rewritten: list[JSONDict] = []
    for message in message_history:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role == "assistant":
            rewritten.append(rewrite_assistant_tool_calls(message))
            continue
        rewritten.append(message)
    return rewritten
