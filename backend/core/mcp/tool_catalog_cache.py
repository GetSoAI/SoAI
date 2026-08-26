"""SoAI - MCP tool catalog cache [backend/core/mcp/tool_catalog_cache.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.mcp.tool_catalog_scope import MCPToolCatalogScope
from core.types.json import JSONDict

__all__ = (
    "MCPToolCatalogCache",
    "MCPToolCatalogCacheEntry",
    "MCPToolCatalogCacheKey",
)


@dataclass(frozen=True, slots=True)
class MCPToolCatalogCacheKey:
    local_version: str
    local_scope: MCPToolCatalogScope
    remote_version: str
    server_filter_signature: tuple[tuple[str, bool], ...]


@dataclass(frozen=True, slots=True)
class MCPToolCatalogCacheEntry:
    key: MCPToolCatalogCacheKey
    tool_entries: tuple[JSONDict, ...]
    tools_by_name: dict[str, JSONDict]


class MCPToolCatalogCache:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._entries: dict[MCPToolCatalogCacheKey, MCPToolCatalogCacheEntry] = {}

    async def get(self, key: MCPToolCatalogCacheKey) -> MCPToolCatalogCacheEntry | None:
        async with self._lock:
            return self._entries.get(key)

    async def set(self, entry: MCPToolCatalogCacheEntry) -> None:
        async with self._lock:
            self._entries[entry.key] = entry
