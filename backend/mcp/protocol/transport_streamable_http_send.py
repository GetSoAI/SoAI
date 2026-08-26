"""SoAI - MCP Streamable HTTP transport send helpers [backend/mcp/protocol/transport_streamable_http_send.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

import httpx2

from core.mcp.mcp_2025_11_25 import MCP_SESSION_ID_HEADER
from core.types.json import JSONDict, JSONValue
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.transport_stream_requests import (
    send_stream_message,
    send_stream_request,
)

__all__ = (
    "send_streamable_http_message",
    "send_streamable_http_request",
)


async def send_streamable_http_request(
    *,
    http_client: httpx2.AsyncClient,
    connection: MCPServerConnection,
    get_headers: Callable[[str | None], dict[str, str]],
    method: str,
    params: JSONDict,
) -> JSONValue | None:
    protocol_version = connection.protocol_version
    headers = get_headers(protocol_version)
    if connection.session_id:
        headers[MCP_SESSION_ID_HEADER] = connection.session_id
    return await send_stream_request(
        http_client=http_client,
        connection=connection,
        url=connection.config.endpoint,
        headers=headers,
        method=method,
        params=params,
    )


async def send_streamable_http_message(
    *,
    http_client: httpx2.AsyncClient,
    connection: MCPServerConnection,
    message: JSONDict,
    get_headers: Callable[[str | None], dict[str, str]],
) -> None:
    headers = get_headers(connection.protocol_version)
    if connection.session_id:
        headers[MCP_SESSION_ID_HEADER] = connection.session_id
    await send_stream_message(
        http_client=http_client,
        connection=connection,
        url=connection.config.endpoint,
        headers=headers,
        message=message,
    )
