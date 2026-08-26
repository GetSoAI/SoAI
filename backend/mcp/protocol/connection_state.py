"""SoAI - MCP server connection state composition [backend/mcp/protocol/connection_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from asyncio.subprocess import Process
from dataclasses import dataclass, field

from core.types.json import JSONDict
from mcp.protocol.connection_request_state import MCPConnectionRequestState
from mcp.protocol.connection_task_state import MCPConnectionTaskState
from mcp.protocol.types import MCPServerConfig, MCPServerStatus

__all__ = ("MCPServerConnection",)


@dataclass(slots=True)
class MCPServerConnection:
    config: MCPServerConfig
    status: MCPServerStatus = MCPServerStatus.DISCONNECTED
    process: Process | None = None
    capabilities: JSONDict | None = None
    protocol_version: str | None = None
    session_id: str | None = None
    last_event_id: str | None = None
    tools: list[JSONDict] = field(default_factory=list[JSONDict])
    resources: list[JSONDict] = field(default_factory=list[JSONDict])
    prompts: list[JSONDict] = field(default_factory=list[JSONDict])
    last_error: str | None = None
    connected_at: float | None = None
    reconnect_attempts: int = 0
    request_state: MCPConnectionRequestState = field(default_factory=MCPConnectionRequestState)
    task_state: MCPConnectionTaskState = field(default_factory=MCPConnectionTaskState)
    io_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
