"""SoAI - MCP tool definitions aggregation [backend/mcp/registry/tools_definitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from core.mcp.catalog_merging import merge_named_catalog_items
from core.mcp.tool_catalog_scope import MCPToolCatalogScope
from mcp.calendar.tool_definitions import build_calendar_tool_definitions
from mcp.mail.tool_definitions import build_mail_tool_definitions
from mcp.rag.tool_definitions import build_mcp_rag_tool_definitions
from mcp.search.definitions import build_mcp_search_tool_definitions
from mcp.tools.utility_definitions import (
    build_internal_utility_tool_definitions,
    build_public_utility_tool_definitions,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_tool_definitions",)


@lru_cache(maxsize=1)
def _build_public_tool_definitions_cached() -> MappingProxyType[str, JSONDict]:
    merged: dict[str, JSONDict] = {}
    merged = merge_named_catalog_items(
        merged,
        build_mcp_rag_tool_definitions(),
        existing_label="tool_definitions",
        incoming_label="rag_tool_definitions",
    )
    merged = merge_named_catalog_items(
        merged,
        build_mcp_search_tool_definitions(),
        existing_label="tool_definitions",
        incoming_label="search_tool_definitions",
    )
    merged = merge_named_catalog_items(
        merged,
        build_mail_tool_definitions(),
        existing_label="tool_definitions",
        incoming_label="mail_tool_definitions",
    )
    merged = merge_named_catalog_items(
        merged,
        build_calendar_tool_definitions(),
        existing_label="tool_definitions",
        incoming_label="calendar_tool_definitions",
    )
    merged = merge_named_catalog_items(
        merged,
        build_public_utility_tool_definitions(),
        existing_label="tool_definitions",
        incoming_label="utility_tool_definitions",
    )
    return MappingProxyType(merged)


@lru_cache(maxsize=1)
def _build_internal_tool_definitions_cached() -> MappingProxyType[str, JSONDict]:
    merged = dict(_build_public_tool_definitions_cached())
    internal_utility_definitions = build_internal_utility_tool_definitions()
    internal_only_definitions = {
        name: definition
        for name, definition in internal_utility_definitions.items()
        if name not in merged
    }
    merged = merge_named_catalog_items(
        merged,
        internal_only_definitions,
        existing_label="tool_definitions",
        incoming_label="internal_utility_tool_definitions",
    )
    return MappingProxyType(merged)


def build_tool_definitions(
    local_scope: MCPToolCatalogScope = "public",
) -> MappingProxyType[str, JSONDict]:
    if local_scope == "internal_admin":
        return _build_internal_tool_definitions_cached()
    return _build_public_tool_definitions_cached()
