"""SoAI - MCP remote service operation methods [backend/mcp/remote/service_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.errors.exceptions import StateError, ValidationError
from core.mcp.protocols_main import MCPServerProtocol
from core.mcp.protocols_storage import MCPServerConfigProtocol
from core.mcp.requests import AddMCPServerRequest
from core.mcp.server_config_normalization import normalize_server_config
from core.security.encryption import decrypt_data
from core.types.json import JSONDict
from mcp.host.internal_protocols import MCPServerHostProtocol
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.types import MCPTransportType
from mcp.remote.capabilities import build_client_capabilities
from mcp.remote.config_coercion import coerce_to_mcp_server_config
from mcp.remote.internal_protocols import MCPRemoteServiceOperationsSurface
from mcp.remote.lifecycle import auto_connect_servers, shutdown_remote_service
from mcp.remote.listings import (
    list_all_prompts,
    list_all_resources,
    list_connected_servers,
)
from mcp.remote.server_operations import (
    add_server,
    get_connected_server,
    invoke_tool,
    read_resource,
    remove_server,
    update_cached_server_config,
)

__all__ = (
    "add_server_method",
    "attach_server_method",
    "auto_connect_servers_method",
    "build_client_capabilities_method",
    "connect_to_server_method",
    "decrypt_mcp_api_key_method",
    "disconnect_from_server_method",
    "get_connected_server_method",
    "invoke_tool_method",
    "list_all_prompts_method",
    "list_all_resources_method",
    "list_connected_servers_method",
    "read_resource_method",
    "remove_server_method",
    "shutdown_method",
    "track_background_task_method",
    "update_cached_server_config_method",
)


def attach_server_method(
    self: MCPRemoteServiceOperationsSurface,
    server: MCPServerProtocol,
) -> None:
    if server is None:
        raise StateError("MCP server is required for host mode tasks.")
    if not isinstance(server, MCPServerHostProtocol):
        raise StateError("MCP server does not support MCP host mode.")
    if self.server is not None and self.server is not server:
        raise StateError("MCP server attachment is already set.")
    self.server = server


def track_background_task_method(
    self: MCPRemoteServiceOperationsSurface,
    task: asyncio.Task[None],
) -> None:
    if task.done():
        return
    _ = self.background_tasks.track(task)


def decrypt_mcp_api_key_method(
    self: MCPRemoteServiceOperationsSurface,
    encrypted: str,
) -> str | None:
    return decrypt_data(self.fernet, encrypted)


def build_client_capabilities_method(self: MCPRemoteServiceOperationsSurface) -> JSONDict:
    return build_client_capabilities(
        host_mode_enabled=self.host_mode_enabled,
        host_roots_list_changed_enabled=self.host_roots_list_changed_enabled,
        host_elicitation_enabled=self.host_elicitation_enabled,
        tasks_enabled=self.tasks_enabled,
        host_sampling_enabled=self.host_sampling_enabled,
    )


async def get_connected_server_method(
    self: MCPRemoteServiceOperationsSurface,
    server_id: str,
) -> MCPServerConnection:
    return await get_connected_server(self.connection_registry, server_id)


async def list_connected_servers_method(self: MCPRemoteServiceOperationsSurface) -> list[JSONDict]:
    return await list_connected_servers(self.connection_registry)


async def list_all_resources_method(self: MCPRemoteServiceOperationsSurface) -> list[JSONDict]:
    return await list_all_resources(self.connection_registry)


async def list_all_prompts_method(self: MCPRemoteServiceOperationsSurface) -> list[JSONDict]:
    return await list_all_prompts(self.connection_registry)


async def invoke_tool_method(
    self: MCPRemoteServiceOperationsSurface,
    server_id: str,
    tool_name: str,
    arguments: JSONDict,
) -> JSONDict:
    send_request = self.send_host_mode_request_for_connection
    return await invoke_tool(
        self.connection_registry,
        self.event_bus,
        send_request,
        server_id,
        tool_name,
        arguments,
    )


async def read_resource_method(
    self: MCPRemoteServiceOperationsSurface,
    server_id: str,
    uri: str,
) -> JSONDict:
    send_request = self.send_host_mode_request_for_connection
    return await read_resource(self.connection_registry, send_request, server_id, uri)


async def add_server_method(
    self: MCPRemoteServiceOperationsSurface,
    request: AddMCPServerRequest,
) -> MCPServerConfigProtocol:
    resolved_transport = (
        request.transport_type
        if isinstance(request.transport_type, MCPTransportType)
        else MCPTransportType(str(request.transport_type))
    )
    added = await add_server(
        self.db_mcp,
        self.event_bus,
        request.name,
        resolved_transport,
        request.endpoint,
        request.arguments,
        request.env,
        request.headers,
        request.api_key,
        request.timeout_ms,
        request.auto_reconnect,
    )
    return normalize_server_config(added)


async def update_cached_server_config_method(
    self: MCPRemoteServiceOperationsSurface,
    config: MCPServerConfigProtocol,
) -> None:
    resolved = coerce_to_mcp_server_config(config)
    await update_cached_server_config(self.connection_registry, resolved)


async def remove_server_method(self: MCPRemoteServiceOperationsSurface, server_id: str) -> bool:
    connection_manager = self.connection_manager
    return await remove_server(
        self.connection_registry,
        connection_manager,
        self.db_mcp,
        self.event_bus,
        server_id,
    )


async def connect_to_server_method(
    self: MCPRemoteServiceOperationsSurface,
    config: MCPServerConfigProtocol,
) -> bool:
    resolved = coerce_to_mcp_server_config(config)
    return await self.connection_manager.connect_to_server(resolved)


async def disconnect_from_server_method(
    self: MCPRemoteServiceOperationsSurface,
    server_id: str,
) -> bool:
    normalized_server_id = server_id.strip()
    if not normalized_server_id:
        raise ValidationError("Server ID is required.")
    return await self.connection_manager.disconnect_from_server(normalized_server_id)


async def auto_connect_servers_method(self: MCPRemoteServiceOperationsSurface) -> None:
    db_mcp = self.db_mcp
    connection_manager = self.connection_manager
    await auto_connect_servers(
        db_mcp_get_all_servers=lambda decrypt: db_mcp.get_all_mcp_servers(decrypt_key=decrypt),
        connection_manager_connect=connection_manager.connect_to_server,
    )


async def shutdown_method(self: MCPRemoteServiceOperationsSurface) -> None:
    await shutdown_remote_service(
        connection_registry=self.connection_registry,
        connection_manager=self.connection_manager,
    )
