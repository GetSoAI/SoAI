"""SoAI - MCP remote connection manager connect operations [backend/mcp/remote/connection_manager_connect_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_mcp import MCPServerConnectedEvent
from core.logging.trace import get_logger
from core.metrics.keyspace_paths_mcp_remote import (
    MCP_REMOTE_COUNTER_CONNECTIONS_FAILED,
    MCP_REMOTE_COUNTER_CONNECTIONS_SUCCESSFUL,
    MCP_REMOTE_COUNTER_CONNECTIONS_TOTAL,
)
from core.timing.epoch import epoch_seconds_float
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.streamable_http_response import (
    MCPStreamAuthorizationError,
    MCPStreamInsufficientScopeError,
)
from mcp.protocol.types import MCPServerConfig, MCPServerStatus, MCPTransportType
from mcp.remote.internal_protocols import MCPConnectionManagerOperationsSurface
from mcp.remote.oauth_auth_errors import (
    extract_mcp_auth_error_details,
    persist_mcp_oauth_auth_error,
)
from mcp.remote.oauth_refresh import maybe_refresh_connection_oauth_token

__all__ = (
    "connect_by_transport_type_method",
    "connect_to_server_method",
    "finalize_connection_method",
)

LOGGER_NAME = "SoAI.mcp.remote.connection_manager_connect_operations"
OPERATION_MCP_REMOTE_CONNECT_TO_SERVER = "mcp.remote.connect_to_server"


async def connect_by_transport_type_method(
    self: MCPConnectionManagerOperationsSurface,
    connection: MCPServerConnection,
) -> bool:
    transport_type = connection.config.transport_type
    if transport_type == MCPTransportType.STDIO:
        return await self.transport_connector.connect_stdio(connection)
    if transport_type == MCPTransportType.STREAMABLE_HTTP:
        return await self.transport_connector.connect_streamable_http(connection)
    raise ValidationError(f"Unsupported transport type: {transport_type}")


async def connect_to_server_method(
    self: MCPConnectionManagerOperationsSurface,
    config: MCPServerConfig,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    self.metrics.increment_counter(*MCP_REMOTE_COUNTER_CONNECTIONS_TOTAL)
    existing_connection: MCPServerConnection | None = None
    connection = MCPServerConnection(config=config, status=MCPServerStatus.CONNECTING)
    registry = self.registry
    async with registry.connections_lock:
        existing_connection = registry.connections.get(config.id)
        if existing_connection and existing_connection.status == MCPServerStatus.CONNECTED:
            logger.debug("Already connected to server %s", config.name)
            return True
        registry.connections[config.id] = connection
    if existing_connection:
        await self.disconnect_connection(
            existing_connection,
            server_id=config.id,
            reason="Replacing existing connection",
        )
    try:
        await maybe_refresh_connection_oauth_token(
            connection=connection,
            db_mcp=self.db_mcp,
            http_client=self.http_client,
            runtime_flags=self.deps.runtime_flags,
            decrypt_secret=self.decrypt_api_key,
            refresh_skew_ms=int(self.oauth_refresh_skew_ms),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="MCP OAuth refresh failed",
            operation=OPERATION_MCP_REMOTE_CONNECT_TO_SERVER,
            details={"server_name": config.name, "server_id": config.id},
        )
        connection.status = MCPServerStatus.AUTH_REQUIRED
        connection.last_error = str(exception)
        await persist_mcp_oauth_auth_error(
            self.db_mcp,
            server_id=config.id,
            status_code=401,
            www_authenticate=None,
            auth_type=config.auth_type,
        )
        self.metrics.increment_counter(*MCP_REMOTE_COUNTER_CONNECTIONS_FAILED)
        return False
    try:
        connected = await self.connect_by_transport_type(connection)
    except (MCPStreamAuthorizationError, MCPStreamInsufficientScopeError) as exception:
        default_status = 403 if isinstance(exception, MCPStreamInsufficientScopeError) else 401
        status_code, www_authenticate = extract_mcp_auth_error_details(
            exception.details,
            default_status=default_status,
        )
        connection.status = MCPServerStatus.AUTH_REQUIRED
        connection.last_error = str(exception)
        await persist_mcp_oauth_auth_error(
            self.db_mcp,
            server_id=config.id,
            status_code=status_code,
            www_authenticate=www_authenticate,
            auth_type=config.auth_type,
        )
        self.metrics.increment_counter(*MCP_REMOTE_COUNTER_CONNECTIONS_FAILED)
        return False
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Error connecting to MCP server",
            operation=OPERATION_MCP_REMOTE_CONNECT_TO_SERVER,
            details={"server_name": config.name, "server_id": config.id},
        )
        connection.status = MCPServerStatus.ERROR
        connection.last_error = str(exception)
        should_update_status = False
        async with registry.connections_lock:
            current = registry.connections.get(config.id)
            should_update_status = current is connection
        if should_update_status:
            await self.update_server_status(config.id, MCPServerStatus.ERROR, str(exception))
        self.metrics.increment_counter(*MCP_REMOTE_COUNTER_CONNECTIONS_FAILED)
        return False
    return await self.finalize_connection(config, connection, connected)


async def finalize_connection_method(
    self: MCPConnectionManagerOperationsSurface,
    config: MCPServerConfig,
    connection: MCPServerConnection,
    connected: bool,
) -> bool:
    logger = get_logger(LOGGER_NAME)
    cleanup_orphaned_connection = False
    tools_count = 0
    resources_count = 0
    registry = self.registry
    async with registry.connections_lock:
        current = registry.connections.get(config.id)
        if current is not connection:
            logger.warning("Connection %s was removed during connect, aborting", config.name)
            cleanup_orphaned_connection = True
        elif connected:
            connection.status = MCPServerStatus.CONNECTED
            connection.connected_at = epoch_seconds_float()
            connection.reconnect_attempts = 0
            connection.task_state.user_disconnected = False
            tools_count = len(connection.tools)
            resources_count = len(connection.resources)
        else:
            connection.status = MCPServerStatus.ERROR
    if cleanup_orphaned_connection:
        await self.cleanup_connection_resources(connection)
        self.metrics.increment_counter(*MCP_REMOTE_COUNTER_CONNECTIONS_FAILED)
        return False
    if connected:
        await self.update_server_status(config.id, MCPServerStatus.CONNECTED)
        await self.event_bus.publish(
            MCPServerConnectedEvent(
                server_id=config.id,
                server_name=config.name,
                tools_count=tools_count,
                resources_count=resources_count,
            ),
        )
        logger.info(
            "Connected to MCP server: %s (%d tools, %d resources)",
            config.name,
            tools_count,
            resources_count,
        )
        self.metrics.increment_counter(*MCP_REMOTE_COUNTER_CONNECTIONS_SUCCESSFUL)
        return True
    await self.update_server_status(config.id, MCPServerStatus.ERROR, "Connection failed")
    self.metrics.increment_counter(*MCP_REMOTE_COUNTER_CONNECTIONS_FAILED)
    return False
