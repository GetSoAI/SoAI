"""SoAI - MCP connection registry dataclass [backend/mcp/registry/connection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.di.validation import require_dependencies
from mcp.protocol.connection_state import MCPServerConnection

__all__ = (
    "MCPConnectionRegistry",
    "MCPConnectionRegistryDependencies",
)


@dataclass(frozen=True, slots=True)
class MCPConnectionRegistryDependencies:
    connections: dict[str, MCPServerConnection]
    connections_lock: asyncio.Lock

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPConnectionRegistryDependencies",
            connections=self.connections,
            connections_lock=self.connections_lock,
        )


class MCPConnectionRegistry:
    def __init__(self, deps: MCPConnectionRegistryDependencies) -> None:
        self.connections = deps.connections
        self.connections_lock = deps.connections_lock
