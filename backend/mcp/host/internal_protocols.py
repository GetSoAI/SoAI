"""SoAI - MCP host internal protocols [backend/mcp/host/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, override, runtime_checkable

from core.mcp.protocols_main import MCPServerProtocol
from core.mcp.protocols_runtime import MCPRemoteHostProtocol

if TYPE_CHECKING:
    from core.mcp.protocols_runtime import MCPPaginationProtocol
    from core.types.json import JSONDict
    from mcp.registry.internal_protocols import MCPTaskServiceProtocol
    from mcp.server.state import MCPServerState

__all__ = (
    "MCPHostContextProtocol",
    "MCPNotificationServiceProtocol",
    "MCPServerHostProtocol",
)


class MCPNotificationServiceProtocol(Protocol):
    async def emit_notification(self, client_id: str, notification: JSONDict) -> None: ...


@runtime_checkable
class MCPServerHostProtocol(MCPServerProtocol, Protocol):
    @property
    def tasks_enabled(self) -> bool: ...

    @property
    def state(self) -> MCPServerState: ...

    @property
    @override
    def pagination(self) -> MCPPaginationProtocol: ...

    @property
    @override
    def task(self) -> MCPTaskServiceProtocol: ...

    @property
    def notification(self) -> MCPNotificationServiceProtocol: ...


class MCPHostContextProtocol(MCPRemoteHostProtocol, Protocol):
    server: MCPServerHostProtocol | None
