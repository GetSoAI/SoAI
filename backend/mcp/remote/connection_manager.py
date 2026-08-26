"""SoAI - MCP remote server connection and reconnection manager [backend/mcp/remote/connection_manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.http_headers import build_mcp_http_headers
from mcp.protocol.types import MCPServerConfig, MCPServerStatus
from mcp.remote.connection_manager_connect_operations import (
    connect_by_transport_type_method,
    connect_to_server_method,
    finalize_connection_method,
)
from mcp.remote.connection_manager_lifecycle_operations import (
    attempt_reconnection_method,
    cleanup_connection_resources_method,
    disconnect_connection_method,
    disconnect_from_server_method,
)
from mcp.remote.dependencies import MCPConnectionManagerDependencies
from mcp.remote.protocol_negotiation import (
    MCPProtocolNegotiator,
    MCPProtocolNegotiatorDependencies,
)
from mcp.remote.reconnection import (
    MCPReconnectionHandler,
    MCPReconnectionHandlerDependencies,
)
from mcp.remote.transport_connector import (
    MCPTransportConnector,
    MCPTransportConnectorDependencies,
)

__all__ = ("MCPConnectionManager",)

LOGGER_NAME = "SoAI.mcp.remote.connection_manager"


class MCPConnectionManager:
    def __init__(self, deps: MCPConnectionManagerDependencies) -> None:
        self.deps = deps
        self.registry = deps.connection_registry
        self.db_mcp = deps.db_mcp
        self.event_bus = deps.event_bus
        self.http_client = deps.http_client
        self.shutdown_event = deps.shutdown_event
        self.metrics = deps.metrics_manager
        self.decrypt_api_key = deps.decrypt_api_key
        self.track_background_task = deps.track_background_task
        self.host_context = deps.host_context
        self.protocol_version = deps.protocol_version
        self.oauth_refresh_skew_ms = deps.oauth_refresh_skew_ms
        self.logger = get_logger(LOGGER_NAME)
        self.negotiator = MCPProtocolNegotiator(
            MCPProtocolNegotiatorDependencies(
                db_mcp=deps.db_mcp,
                decrypt_api_key=deps.decrypt_api_key,
                build_client_capabilities=deps.build_client_capabilities,
                send_host_mode_message=deps.send_host_mode_message,
                protocol_version=deps.protocol_version,
            ),
        )
        self.reconnection_handler = MCPReconnectionHandler(
            MCPReconnectionHandlerDependencies(
                db_mcp=deps.db_mcp,
                event_bus=deps.event_bus,
                shutdown_event=deps.shutdown_event,
                connect_by_transport=self.connect_by_transport_type,
                max_reconnect_attempts=deps.max_reconnect_attempts,
                reconnect_delay=deps.reconnect_delay,
            ),
        )
        self.transport_connector = MCPTransportConnector(
            MCPTransportConnectorDependencies(
                http_client=deps.http_client,
                db_mcp=deps.db_mcp,
                runtime_flags=deps.runtime_flags,
                shutdown_event=deps.shutdown_event,
                event_publish=deps.event_bus.publish,
                track_background_task=deps.track_background_task,
                host_context=deps.host_context,
                protocol_version=deps.protocol_version,
                negotiator=self.negotiator,
                attempt_reconnection=self.attempt_reconnection,
                cleanup_connection_resources=self.cleanup_connection_resources,
                build_http_headers=self.build_http_headers,
                logger=self.logger,
            ),
        )

    def build_http_headers(
        self,
        config: MCPServerConfig,
        protocol_version: str | None,
    ) -> dict[str, str]:
        return build_mcp_http_headers(
            config,
            protocol_version=protocol_version or self.protocol_version,
            decrypt_secret=self.decrypt_api_key,
        )

    async def cleanup_connection_resources(self, connection: MCPServerConnection) -> None:
        await cleanup_connection_resources_method(self, connection)

    async def disconnect_connection(
        self,
        connection: MCPServerConnection,
        *,
        server_id: str,
        reason: str,
    ) -> bool:
        return await disconnect_connection_method(
            self,
            connection,
            server_id=server_id,
            reason=reason,
        )

    async def connect_by_transport_type(self, connection: MCPServerConnection) -> bool:
        return await connect_by_transport_type_method(self, connection)

    async def connect_to_server(self, config: MCPServerConfig) -> bool:
        return await connect_to_server_method(self, config)

    async def finalize_connection(
        self,
        config: MCPServerConfig,
        connection: MCPServerConnection,
        connected: bool,
    ) -> bool:
        return await finalize_connection_method(self, config, connection, connected)

    async def disconnect_from_server(self, server_id: str) -> bool:
        return await disconnect_from_server_method(self, server_id)

    async def attempt_reconnection(self, connection: MCPServerConnection) -> bool:
        return await attempt_reconnection_method(self, connection)

    async def update_server_status(
        self,
        server_id: str,
        status: MCPServerStatus,
        error: str | None = None,
    ) -> None:
        await self.db_mcp.update_mcp_server_status(server_id, status.value, error)
