"""SoAI - MCP local tool catalog visibility scope [backend/core/mcp/tool_catalog_scope.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE",
    "PUBLIC_MCP_TOOL_CATALOG_SCOPE",
    "MCPToolCatalogScope",
)

MCPToolCatalogScope = str

PUBLIC_MCP_TOOL_CATALOG_SCOPE: MCPToolCatalogScope = "public"
INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE: MCPToolCatalogScope = "internal_admin"
