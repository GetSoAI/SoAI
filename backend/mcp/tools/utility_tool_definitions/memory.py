"""SoAI - MCP utility tool definitions: memory knowledge graph [backend/mcp/tools/utility_tool_definitions/memory.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.schema import build_tool_icon_entry
from mcp.tools.icons import ICON_MEMORY
from mcp.tools.utility_tool_definitions.memory_recall_forget import (
    build_memory_forget_tool,
    build_memory_recall_tool,
)
from mcp.tools.utility_tool_definitions.memory_store_search import (
    build_memory_search_tool,
    build_memory_store_tool,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_memory_tool_definitions",)


def _memory_icon() -> JSONDict:
    return build_tool_icon_entry(ICON_MEMORY)


def build_memory_tool_definitions() -> dict[str, JSONDict]:
    icon = _memory_icon()
    return {
        "memory_store": build_memory_store_tool(icon),
        "memory_search": build_memory_search_tool(icon),
        "memory_recall": build_memory_recall_tool(icon),
        "memory_forget": build_memory_forget_tool(icon),
    }
