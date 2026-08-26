"""SoAI - Tool exchange digests for context compaction [backend/features/agent/runtime/context_compaction/tool_digests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.agent.tool_call_fields import resolve_tool_call_name
from core.serialization.json_parsing import parse_json_value_or_none
from features.agent.runtime.context_compaction.text import truncate_compaction_line
from features.agent.runtime.context_compaction.tool_digests_browser import (
    digest_browser_tool_exchange,
)
from features.agent.runtime.context_compaction.tool_digests_workspace import (
    digest_workspace_tool_exchange,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("digest_tool_exchange",)


def _parse_json_dict(text: str) -> JSONDict | None:
    parsed = parse_json_value_or_none(text)
    if not isinstance(parsed, dict):
        return None
    return parsed


def _parse_tool_arguments(tool_call: JSONDict) -> JSONDict | None:
    arguments_text = tool_call.get("arguments")
    if not isinstance(arguments_text, str):
        function_value = tool_call.get("function")
        if isinstance(function_value, dict):
            arguments_text = function_value.get("arguments")
    if not isinstance(arguments_text, str):
        return None
    return _parse_json_dict(arguments_text)


def digest_tool_exchange(tool_call: JSONDict, tool_message: JSONDict | None) -> list[str]:
    tool_name = resolve_tool_call_name(tool_call) or "tool"
    tool_arguments = _parse_tool_arguments(tool_call)
    content_value = tool_message.get("content") if isinstance(tool_message, dict) else None
    content_text = content_value if isinstance(content_value, str) else ""
    tool_result = _parse_json_dict(content_text)
    if tool_result is None:
        return (
            [f"{tool_name}: {truncate_compaction_line(content_text, max_chars=240)}"]
            if content_text.strip()
            else []
        )
    browser = digest_browser_tool_exchange(
        tool_name,
        tool_arguments,
        tool_result,
        truncate_line=truncate_compaction_line,
    )
    if browser is not None:
        return browser
    workspace = digest_workspace_tool_exchange(
        tool_name,
        tool_arguments,
        tool_result,
        truncate_line=truncate_compaction_line,
    )
    return workspace if workspace is not None else []
