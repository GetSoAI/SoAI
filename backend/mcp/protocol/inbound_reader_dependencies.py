"""SoAI - Shared dependency bundle for MCP inbound message readers [backend/mcp/protocol/inbound_reader_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.events.types_base import Event
from mcp.host.internal_protocols import MCPHostContextProtocol
from mcp.protocol.connection_state import MCPServerConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("MCPInboundReaderDependencies",)


@dataclass(frozen=True, slots=True)
class MCPInboundReaderDependencies:
    host_context: MCPHostContextProtocol
    shutdown_event: asyncio.Event
    handle_host_mode_request: Callable[
        [MCPHostContextProtocol, MCPServerConnection, JSONDict],
        Awaitable[None],
    ]
    handle_host_mode_notification: Callable[
        [MCPHostContextProtocol, MCPServerConnection, JSONDict],
        Awaitable[None],
    ]
    publish_event: Callable[[Event], Awaitable[None]]
    attempt_reconnection: Callable[[MCPServerConnection], Coroutine[None, None, bool]]
    track_background_task: Callable[[asyncio.Task[None]], None]

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPInboundReaderDependencies",
            attempt_reconnection=self.attempt_reconnection,
            handle_host_mode_notification=self.handle_host_mode_notification,
            handle_host_mode_request=self.handle_host_mode_request,
            host_context=self.host_context,
            publish_event=self.publish_event,
            shutdown_event=self.shutdown_event,
            track_background_task=self.track_background_task,
        )
