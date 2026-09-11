"""SoAI - MCP tool definitions aggregation [backend/mcp/registry/tools_definitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.mcp.catalog_merging import merge_named_catalog_items
from core.mcp.tool_catalog_scope import (
    CONVERSATION_MCP_TOOL_CATALOG_SCOPE,
    INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE,
    MCPToolCatalogScope,
)
from mcp.calendar.tool_definitions import build_calendar_tool_definitions
from mcp.mail.tool_definitions import build_mail_tool_definitions
from mcp.rag.tool_definitions import build_mcp_rag_tool_definitions
from mcp.search.definitions import build_mcp_search_tool_definitions
from mcp.tools.utility_definitions import (
    build_conversation_utility_tool_definitions,
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
def _build_conversation_tool_definitions_cached() -> MappingProxyType[str, JSONDict]:
    return _extend_tool_definitions(
        _build_public_tool_definitions_cached(),
        build_conversation_utility_tool_definitions(),
        incoming_label="conversation_utility_tool_definitions",
    )


def _extend_tool_definitions(
    base: MappingProxyType[str, JSONDict],
    utility_definitions: dict[str, JSONDict],
    *,
    incoming_label: str,
) -> MappingProxyType[str, JSONDict]:
    for name in base.keys() & utility_definitions.keys():
        if base[name] != utility_definitions[name]:
            raise ValidationError(f"Conflicting definition for {name!r} in {incoming_label}")
    additions = {
        name: definition for name, definition in utility_definitions.items() if name not in base
    }
    merged = merge_named_catalog_items(
        dict(base),
        additions,
        existing_label="tool_definitions",
        incoming_label=incoming_label,
    )
    return MappingProxyType(merged)


@lru_cache(maxsize=1)
def _build_internal_tool_definitions_cached() -> MappingProxyType[str, JSONDict]:
    return _extend_tool_definitions(
        _build_conversation_tool_definitions_cached(),
        build_internal_utility_tool_definitions(),
        incoming_label="internal_utility_tool_definitions",
    )


def build_tool_definitions(
    local_scope: MCPToolCatalogScope = "public",
) -> MappingProxyType[str, JSONDict]:
    if local_scope == INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE:
        return _build_internal_tool_definitions_cached()
    if local_scope == CONVERSATION_MCP_TOOL_CATALOG_SCOPE:
        return _build_conversation_tool_definitions_cached()
    return _build_public_tool_definitions_cached()
