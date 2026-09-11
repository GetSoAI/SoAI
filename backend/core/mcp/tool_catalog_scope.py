"""SoAI - MCP local tool catalog visibility scope [backend/core/mcp/tool_catalog_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "CONVERSATION_MCP_TOOL_CATALOG_SCOPE",
    "INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE",
    "PUBLIC_MCP_TOOL_CATALOG_SCOPE",
    "MCPToolCatalogScope",
    "resolve_conversation_tool_catalog_scope",
)

MCPToolCatalogScope = str

PUBLIC_MCP_TOOL_CATALOG_SCOPE: MCPToolCatalogScope = "public"
CONVERSATION_MCP_TOOL_CATALOG_SCOPE: MCPToolCatalogScope = "conversation"
INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE: MCPToolCatalogScope = "internal_admin"


def resolve_conversation_tool_catalog_scope(
    *,
    user_is_admin: bool,
) -> MCPToolCatalogScope:
    if user_is_admin is True:
        return INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE
    return CONVERSATION_MCP_TOOL_CATALOG_SCOPE
