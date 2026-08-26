"""SoAI - MCP session activity helpers [backend/mcp/server/handlers/session_activity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.state import MCPSessionState

__all__ = ("touch_session_last_activity",)


async def touch_session_last_activity(session_state: MCPSessionState, session_id: str) -> None:
    async with session_state.client_sessions_lock:
        session = session_state.client_sessions.get(session_id)
        if session:
            session.last_activity = time.monotonic()
