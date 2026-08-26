"""SoAI - MCP connection request state management [backend/mcp/protocol/connection_request_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from core.types.json import JSONValue

__all__ = (
    "cancel_pending_request",
    "MCPConnectionRequestState",
    "cancel_all_pending_requests",
    "create_pending_request",
    "pop_pending_request",
)


@dataclass(slots=True)
class MCPConnectionRequestState:
    message_id: int = 0
    pending_requests: dict[int, asyncio.Future[JSONValue]] = field(
        default_factory=dict[int, asyncio.Future[JSONValue]],
    )
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


async def create_pending_request(
    state: MCPConnectionRequestState,
) -> tuple[int, asyncio.Future[JSONValue]]:
    async with state.lock:
        state.message_id += 1
        request_id = state.message_id
        future: asyncio.Future[JSONValue] = asyncio.get_running_loop().create_future()
        state.pending_requests[request_id] = future
        return (request_id, future)


async def pop_pending_request(
    state: MCPConnectionRequestState,
    message_id: int,
) -> asyncio.Future[JSONValue] | None:
    async with state.lock:
        return state.pending_requests.pop(message_id, None)


async def cancel_pending_request(state: MCPConnectionRequestState, message_id: int) -> None:
    future = await pop_pending_request(state, message_id)
    if future is not None and not future.done():
        future.cancel()


async def cancel_all_pending_requests(state: MCPConnectionRequestState) -> None:
    async with state.lock:
        pending = list(state.pending_requests.values())
        state.pending_requests.clear()
    for future in pending:
        if not future.done():
            future.cancel()
