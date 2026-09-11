"""SoAI - MCP cross-subsystem protocol contracts and exports [backend/core/mcp/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.mcp.protocols_main import (
    MCPRegistrationProtocol,
    MCPRemoteProtocol,
    MCPSearchApiKeysProtocol,
    MCPSearchProtocol,
    MCPServerProtocol,
    MCPServicesCoordinatorProtocol,
)
from core.mcp.protocols_rag import (
    FetchedContentProtocol,
    MCPRAGProtocol,
    MCPRAGStorageProtocol,
)
from core.mcp.protocols_runtime import (
    MCPClientSessionProtocol,
    MCPContextProtocol,
    MCPPaginationProtocol,
    MCPRemoteHostProtocol,
    MCPSessionProtocol,
    MCPStreamingProtocol,
    MCPTaskProtocol,
)
from core.mcp.protocols_storage import (
    DatabaseMCPProtocol,
    DatabaseMemoryProtocol,
    MCPServerConfigProtocol,
)
from core.mcp.tool_catalog_cache import MCPToolCatalogCache
from core.mcp.tool_catalog_scope import MCPToolCatalogScope
from core.plugins.protocols_database import DatabasePluginsProtocol

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "DatabaseMCPProtocol",
    "DatabaseMemoryProtocol",
    "DatabasePluginsProtocol",
    "FetchedContentProtocol",
    "MCPClientSessionProtocol",
    "MCPContextProtocol",
    "MCPPaginationProtocol",
    "MCPRAGProtocol",
    "MCPRAGStorageProtocol",
    "MCPRegistrationProtocol",
    "MCPRemoteHostProtocol",
    "MCPRemoteProtocol",
    "MCPRemoteToolCatalogProtocol",
    "MCPSearchApiKeysProtocol",
    "MCPSearchProtocol",
    "MCPServerConfigProtocol",
    "MCPServerProtocol",
    "MCPServerToolCatalogProtocol",
    "MCPServicesCoordinatorProtocol",
    "MCPSessionProtocol",
    "MCPStreamingProtocol",
    "MCPTaskProtocol",
    "MCPToolCatalogSourcesProtocol",
    "MCPToolRegistrationViewProtocol",
)


class MCPToolRegistrationViewProtocol(Protocol):
    def registered_tool_names(self) -> list[str]: ...

    def available_local_tool_names(
        self,
        local_scope: MCPToolCatalogScope = "public",
    ) -> list[str]: ...

    def tool_definitions(
        self,
        local_scope: MCPToolCatalogScope = "public",
    ) -> dict[str, JSONDict]: ...


class MCPServerToolCatalogProtocol(Protocol):
    @property
    def registration(self) -> MCPToolRegistrationViewProtocol: ...


class MCPRemoteToolCatalogProtocol(Protocol):
    async def tool_catalog_version(self) -> str: ...

    async def list_all_tools(self) -> list[JSONDict]: ...


class MCPToolCatalogSourcesProtocol(Protocol):
    @property
    def mcp_server(self) -> MCPServerProtocol: ...

    @property
    def mcp_remote(self) -> MCPRemoteProtocol: ...

    @property
    def mcp_tool_catalog_cache(self) -> MCPToolCatalogCache: ...
