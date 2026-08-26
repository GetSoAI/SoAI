"""SoAI - MCP remote public operations [backend/mcp/remote/public_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine

from core.mcp.protocols_main import MCPServerProtocol
from core.mcp.protocols_storage import MCPServerConfigProtocol
from core.mcp.requests import AddMCPServerRequest
from core.types.json import JSONDict, JSONValue
from mcp.protocol.connection_state import MCPServerConnection
from mcp.remote.host_state_operations import (
    clear_pending_url_elicitation_for_task_method,
    clear_pending_url_elicitation_method,
    get_host_roots_method,
    initialize_state_managers_method,
    normalize_roots_method,
    record_pending_url_elicitation_method,
    set_host_roots_method,
    start_method,
)
from mcp.remote.internal_protocols import (
    MCPRemoteHostModeMessagingSurface,
    MCPRemoteHostStateSurface,
    MCPRemoteServiceOperationsSurface,
    MCPRemoteToolCatalogSurface,
)
from mcp.remote.oauth_public_operations import MCPRemoteOAuthOperations
from mcp.remote.service_background_tasks import schedule_background_task_method
from mcp.remote.service_host_mode_messaging_operations import (
    send_host_mode_message_for_connection_method,
    send_host_mode_message_method,
    send_host_mode_request_for_connection_method,
    send_host_mode_request_method,
)
from mcp.remote.service_operations import (
    add_server_method,
    attach_server_method,
    auto_connect_servers_method,
    build_client_capabilities_method,
    connect_to_server_method,
    decrypt_mcp_api_key_method,
    disconnect_from_server_method,
    get_connected_server_method,
    invoke_tool_method,
    list_all_prompts_method,
    list_all_resources_method,
    list_connected_servers_method,
    read_resource_method,
    remove_server_method,
    shutdown_method,
    track_background_task_method,
    update_cached_server_config_method,
)
from mcp.remote.tool_catalog import list_all_tools_method, tool_catalog_version_method

__all__ = ("MCPRemoteOperations",)


class MCPRemoteOperations(MCPRemoteOAuthOperations):
    async def list_all_tools(self: MCPRemoteToolCatalogSurface) -> list[JSONDict]:
        return await list_all_tools_method(self)

    async def tool_catalog_version(self: MCPRemoteToolCatalogSurface) -> str:
        return await tool_catalog_version_method(self)

    def initialize_state_managers(self: MCPRemoteHostStateSurface) -> None:
        initialize_state_managers_method(self)

    def normalize_roots(
        self: MCPRemoteHostStateSurface,
        roots: list[JSONValue] | None = None,
    ) -> list[JSONDict]:
        return normalize_roots_method(self, roots)

    def get_host_roots(self: MCPRemoteHostStateSurface) -> list[JSONDict]:
        return get_host_roots_method(self)

    async def set_host_roots(
        self: MCPRemoteHostStateSurface,
        roots: list[JSONValue],
    ) -> list[JSONDict]:
        return await set_host_roots_method(self, roots)

    async def record_pending_url_elicitation(
        self: MCPRemoteHostStateSurface,
        server_id: str,
        elicitation_id: str,
        task_id: str,
    ) -> None:
        await record_pending_url_elicitation_method(self, server_id, elicitation_id, task_id)

    async def clear_pending_url_elicitation(
        self: MCPRemoteHostStateSurface,
        client_id: str,
        elicitation_id: str,
    ) -> bool:
        return await clear_pending_url_elicitation_method(self, client_id, elicitation_id)

    async def clear_pending_url_elicitation_for_task(
        self: MCPRemoteHostStateSurface,
        client_id: str,
        elicitation_id: str,
        task_id: str,
    ) -> bool:
        return await clear_pending_url_elicitation_for_task_method(
            self,
            client_id,
            elicitation_id,
            task_id,
        )

    async def start(self: MCPRemoteHostStateSurface) -> None:
        await start_method(self)

    def attach_server(self: MCPRemoteServiceOperationsSurface, server: MCPServerProtocol) -> None:
        attach_server_method(self, server)

    def track_background_task(
        self: MCPRemoteServiceOperationsSurface,
        task: asyncio.Task[None],
    ) -> None:
        track_background_task_method(self, task)

    def decrypt_mcp_api_key(self: MCPRemoteServiceOperationsSurface, encrypted: str) -> str | None:
        return decrypt_mcp_api_key_method(self, encrypted)

    def build_client_capabilities(self: MCPRemoteServiceOperationsSurface) -> JSONDict:
        return build_client_capabilities_method(self)

    async def send_host_mode_message_for_connection(
        self: MCPRemoteHostModeMessagingSurface,
        connection: MCPServerConnection,
        message: JSONDict,
    ) -> None:
        await send_host_mode_message_for_connection_method(self, connection, message)

    async def send_host_mode_request_for_connection(
        self: MCPRemoteHostModeMessagingSurface,
        connection: MCPServerConnection,
        method: str,
        parameters: JSONDict,
    ) -> JSONValue | None:
        return await send_host_mode_request_for_connection_method(
            self,
            connection,
            method,
            parameters,
        )

    async def send_host_mode_message(
        self: MCPRemoteHostModeMessagingSurface,
        server_id: str,
        message: JSONDict,
    ) -> None:
        await send_host_mode_message_method(self, server_id, message)

    async def send_host_mode_request(
        self: MCPRemoteHostModeMessagingSurface,
        server_id: str,
        method: str,
        parameters: JSONDict,
    ) -> JSONValue:
        return await send_host_mode_request_method(self, server_id, method, parameters)

    async def get_connected_server(
        self: MCPRemoteServiceOperationsSurface,
        server_id: str,
    ) -> MCPServerConnection:
        return await get_connected_server_method(self, server_id)

    async def list_connected_servers(self: MCPRemoteServiceOperationsSurface) -> list[JSONDict]:
        return await list_connected_servers_method(self)

    async def list_all_resources(self: MCPRemoteServiceOperationsSurface) -> list[JSONDict]:
        return await list_all_resources_method(self)

    async def list_all_prompts(self: MCPRemoteServiceOperationsSurface) -> list[JSONDict]:
        return await list_all_prompts_method(self)

    async def invoke_tool(
        self: MCPRemoteServiceOperationsSurface,
        server_id: str,
        tool_name: str,
        arguments: JSONDict,
    ) -> JSONDict:
        return await invoke_tool_method(self, server_id, tool_name, arguments)

    async def read_resource(
        self: MCPRemoteServiceOperationsSurface,
        server_id: str,
        uri: str,
    ) -> JSONDict:
        return await read_resource_method(self, server_id, uri)

    async def add_server(
        self: MCPRemoteServiceOperationsSurface,
        request: AddMCPServerRequest,
    ) -> MCPServerConfigProtocol:
        return await add_server_method(self, request)

    async def update_cached_server_config(
        self: MCPRemoteServiceOperationsSurface,
        config: MCPServerConfigProtocol,
    ) -> None:
        await update_cached_server_config_method(self, config)

    async def remove_server(self: MCPRemoteServiceOperationsSurface, server_id: str) -> bool:
        return await remove_server_method(self, server_id)

    async def connect_to_server(
        self: MCPRemoteServiceOperationsSurface,
        config: MCPServerConfigProtocol,
    ) -> bool:
        return await connect_to_server_method(self, config)

    async def disconnect_from_server(
        self: MCPRemoteServiceOperationsSurface,
        server_id: str,
    ) -> bool:
        return await disconnect_from_server_method(self, server_id)

    async def auto_connect_servers(self: MCPRemoteServiceOperationsSurface) -> None:
        await auto_connect_servers_method(self)

    async def shutdown(self: MCPRemoteServiceOperationsSurface) -> None:
        await shutdown_method(self)

    def schedule_background_task(
        self: MCPRemoteServiceOperationsSurface,
        coro: Coroutine[None, None, None],
        *,
        name: str,
    ) -> asyncio.Task[None]:
        return schedule_background_task_method(self, coro, name=name)
