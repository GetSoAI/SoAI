"""SoAI - MCP connection task state dataclass [backend/mcp/protocol/connection_task_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

__all__ = ("MCPConnectionTaskState",)


@dataclass(slots=True)
class MCPConnectionTaskState:
    reader_task: asyncio.Task[None] | None = None
    reconnect_task: asyncio.Task[None] | None = None
    oauth_refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    initialized: bool = False
    user_disconnected: bool = False
