"""SoAI - MCP remote host-mode message and request dispatch [backend/mcp/remote/messaging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.transport_stdio import send_stdio_message, send_stdio_request
from mcp.protocol.transport_streamable_http_send import (
    send_streamable_http_message,
    send_streamable_http_request,
)
from mcp.protocol.types import MCPJSONRPCError, MCPServerConfig, MCPTransportType

if TYPE_CHECKING:
    import httpx2

    from core.types.json import JSONDict, JSONValue

__all__ = (
    "send_host_mode_message",
    "send_host_mode_request",
)


async def send_host_mode_message(
    http_client: httpx2.AsyncClient,
    connection: MCPServerConnection,
    message: JSONDict,
    build_http_headers: Callable[[MCPServerConfig, str | None], dict[str, str]],
) -> None:
    transport = connection.config.transport_type
    if transport == MCPTransportType.STDIO:
        await send_stdio_message(connection, message)
    elif transport == MCPTransportType.STREAMABLE_HTTP:
        await send_streamable_http_message(
            http_client=http_client,
            connection=connection,
            message=message,
            get_headers=lambda ver: build_http_headers(connection.config, ver),
        )
        return
    raise MCPJSONRPCError(-32603, f"Unsupported transport: {transport.value}")


async def send_host_mode_request(
    http_client: httpx2.AsyncClient,
    connection: MCPServerConnection,
    method: str,
    parameters: JSONDict,
    build_http_headers: Callable[[MCPServerConfig, str | None], dict[str, str]],
) -> JSONValue | None:
    transport = connection.config.transport_type
    if transport == MCPTransportType.STDIO:
        return await send_stdio_request(connection, method, parameters)
    if transport == MCPTransportType.STREAMABLE_HTTP:
        return await send_streamable_http_request(
            http_client=http_client,
            connection=connection,
            get_headers=lambda ver: build_http_headers(connection.config, ver),
            method=method,
            params=parameters,
        )
    raise MCPJSONRPCError(-32603, f"Unsupported transport: {transport.value}")
