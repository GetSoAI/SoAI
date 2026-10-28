"""SoAI - MCP protocol internal protocols [backend/mcp/protocol/internal_protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.types.json import JSONDict

__all__ = ("StdinDrainProtocol", "MCPNotificationSender")


class StdinDrainProtocol(Protocol):
    def write(self, data: bytes) -> None: ...

    async def drain(self) -> None: ...


class MCPNotificationSender(Protocol):
    async def __call__(self, *, message: JSONDict) -> None: ...
