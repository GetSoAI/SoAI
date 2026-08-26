"""SoAI - MCP remote host-mode messaging operations [backend/mcp/remote/service_host_mode_messaging_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import StateError
from core.types.json import JSONDict, JSONValue
from mcp.protocol.connection_state import MCPServerConnection
from mcp.remote.host_mode_auth_retry import (
    send_host_mode_message_with_auth_retry,
    send_host_mode_request_with_auth_retry,
)
from mcp.remote.internal_protocols import MCPRemoteHostModeMessagingSurface
from mcp.remote.messaging import send_host_mode_message, send_host_mode_request
from mcp.remote.oauth_refresh import maybe_refresh_connection_oauth_token

__all__ = (
    "send_host_mode_message_for_connection_method",
    "send_host_mode_message_method",
    "send_host_mode_request_for_connection_method",
    "send_host_mode_request_method",
)


async def send_host_mode_message_for_connection_method(
    self: MCPRemoteHostModeMessagingSurface,
    connection: MCPServerConnection,
    message: JSONDict,
) -> None:
    if connection is None:
        raise StateError("MCP connection is required.")
    connection_manager = self.connection_manager
    await maybe_refresh_connection_oauth_token(
        connection=connection,
        db_mcp=self.db_mcp,
        http_client=self.http_client,
        runtime_flags=self.runtime_flags,
        decrypt_secret=self.decrypt_mcp_api_key,
        refresh_skew_ms=int(connection_manager.oauth_refresh_skew_ms),
    )

    async def _send(message_value: JSONDict) -> None:
        await send_host_mode_message(
            self.http_client,
            connection,
            message_value,
            connection_manager.build_http_headers,
        )

    await send_host_mode_message_with_auth_retry(
        connection=connection,
        message=message,
        db_mcp=self.db_mcp,
        http_client=self.http_client,
        runtime_flags=self.runtime_flags,
        decrypt_secret=self.decrypt_mcp_api_key,
        cleanup_connection_resources=connection_manager.cleanup_connection_resources,
        send_message=_send,
    )


async def send_host_mode_request_for_connection_method(
    self: MCPRemoteHostModeMessagingSurface,
    connection: MCPServerConnection,
    method: str,
    parameters: JSONDict,
) -> JSONValue | None:
    if connection is None:
        raise StateError("MCP connection is required.")
    connection_manager = self.connection_manager
    await maybe_refresh_connection_oauth_token(
        connection=connection,
        db_mcp=self.db_mcp,
        http_client=self.http_client,
        runtime_flags=self.runtime_flags,
        decrypt_secret=self.decrypt_mcp_api_key,
        refresh_skew_ms=int(connection_manager.oauth_refresh_skew_ms),
    )

    async def _send(method_value: str, params_value: JSONDict) -> JSONValue | None:
        return await send_host_mode_request(
            self.http_client,
            connection,
            method_value,
            params_value,
            connection_manager.build_http_headers,
        )

    return await send_host_mode_request_with_auth_retry(
        connection=connection,
        method=method,
        parameters=parameters,
        db_mcp=self.db_mcp,
        http_client=self.http_client,
        runtime_flags=self.runtime_flags,
        decrypt_secret=self.decrypt_mcp_api_key,
        cleanup_connection_resources=connection_manager.cleanup_connection_resources,
        send_request=_send,
    )


async def send_host_mode_message_method(
    self: MCPRemoteHostModeMessagingSurface,
    server_id: str,
    message: JSONDict,
) -> None:
    connection = await self.get_connected_server(server_id)
    await self.send_host_mode_message_for_connection(connection, message)


async def send_host_mode_request_method(
    self: MCPRemoteHostModeMessagingSurface,
    server_id: str,
    method: str,
    parameters: JSONDict,
) -> JSONValue:
    connection = await self.get_connected_server(server_id)
    result = await self.send_host_mode_request_for_connection(connection, method, parameters)
    return result if result is not None else {}
