"""SoAI - Agent prompt filtering by selected tools [backend/features/agent/runtime/tool_prompt_filter.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.mcp.default_tool_names import (
    DEFAULT_AUTOMATION_MCP_EXECUTE_TOOLS,
    DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS,
    DEFAULT_CONVERSATION_MCP_PLAN_TOOLS,
    DEFAULT_CONVERSATION_MCP_TOOLS,
    DEFAULT_MCP_SERVER_EXPOSED_TOOLS,
)
from core.mcp.qualified_name import decode_qualified_tool_name

__all__ = (
    "filter_prompt_lines_by_selected_tools",
    "normalize_selected_tool_names",
)

_TOOL_NAME_PATTERN_TEXT = r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"


def _resolve_known_tool_names() -> frozenset[str]:
    return frozenset(
        decode_qualified_tool_name(tool_name)[1]
        for tool_name in (
            *DEFAULT_MCP_SERVER_EXPOSED_TOOLS,
            *DEFAULT_CONVERSATION_MCP_TOOLS,
            *DEFAULT_CONVERSATION_MCP_PLAN_TOOLS,
            *DEFAULT_CONVERSATION_MCP_EXECUTE_TOOLS,
            *DEFAULT_AUTOMATION_MCP_EXECUTE_TOOLS,
        )
    )


def normalize_selected_tool_names(tool_names: list[str] | tuple[str, ...]) -> frozenset[str]:
    return frozenset(
        decoded_name
        for tool_name in tool_names
        for decoded_name in (decode_qualified_tool_name(str(tool_name or "").strip())[1],)
        if decoded_name
    )


def filter_prompt_lines_by_selected_tools(*, text: str, selected_tools: frozenset[str]) -> str:
    kept_lines: list[str] = []
    known_tool_names = _resolve_known_tool_names()
    for line in text.splitlines():
        mentioned_tools = (
            frozenset(match.group(0) for match in re.finditer(_TOOL_NAME_PATTERN_TEXT, line))
            & known_tool_names
        )
        if mentioned_tools and not mentioned_tools.issubset(selected_tools):
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines).strip()
