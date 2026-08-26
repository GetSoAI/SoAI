"""SoAI - MCP remote transport connectors [backend/mcp/remote/transport_connector.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx2

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.system.async_process_spawning import spawn_async_process
from core.system.subprocess_env import build_minimal_subprocess_env
from mcp.host.internal_protocols import MCPHostContextProtocol
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.inbound_reader_dependencies import MCPInboundReaderDependencies
from mcp.protocol.transport_stdio import send_stdio_request, stdio_reader
from mcp.protocol.transport_streamable_http_connect import (
    MCPStreamableHTTPNotSupportedError,
    connect_streamable_http_transport,
)
from mcp.protocol.types import MCPServerConfig
from mcp.registry.host_dispatch import (
    handle_host_mode_notification,
    handle_host_mode_request,
)
from mcp.remote.oauth_auth_errors import persist_mcp_oauth_auth_error
from mcp.remote.protocol_negotiation import MCPProtocolNegotiator

if TYPE_CHECKING:
    from core.mcp.protocols_storage import DatabaseMCPProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "MCPTransportConnector",
    "MCPTransportConnectorDependencies",
)

OPERATION = "mcp.remote.connect_stdio"


@dataclass(frozen=True, slots=True)
class MCPTransportConnectorDependencies:
    http_client: httpx2.AsyncClient
    db_mcp: DatabaseMCPProtocol
    runtime_flags: RuntimeFlagsViewProtocol
    shutdown_event: asyncio.Event
    event_publish: Callable[[Event], Awaitable[None]]
    track_background_task: Callable[[asyncio.Task[None]], None]
    host_context: MCPHostContextProtocol
    protocol_version: str
    negotiator: MCPProtocolNegotiator
    attempt_reconnection: Callable[[MCPServerConnection], Coroutine[None, None, bool]]
    cleanup_connection_resources: Callable[[MCPServerConnection], Awaitable[None]]
    build_http_headers: Callable[[MCPServerConfig, str | None], dict[str, str]]
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="MCPTransportConnectorDependencies",
            attempt_reconnection=self.attempt_reconnection,
            build_http_headers=self.build_http_headers,
            cleanup_connection_resources=self.cleanup_connection_resources,
            db_mcp=self.db_mcp,
            event_publish=self.event_publish,
            host_context=self.host_context,
            http_client=self.http_client,
            logger=self.logger,
            negotiator=self.negotiator,
            protocol_version=self.protocol_version,
            runtime_flags=self.runtime_flags,
            shutdown_event=self.shutdown_event,
            track_background_task=self.track_background_task,
        )


class MCPTransportConnector:

    def __init__(self, deps: MCPTransportConnectorDependencies) -> None:
        self._deps = deps

    async def connect_stdio(self, connection: MCPServerConnection) -> bool:
        try:
            connection.process = await spawn_async_process(
                [connection.config.endpoint, *(connection.config.args or [])],
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=build_minimal_subprocess_env(
                    overrides={
                        "PYTHONUNBUFFERED": "1",
                        **(connection.config.env or {}),
                    },
                ),
            )
            inbound = MCPInboundReaderDependencies(
                host_context=self._deps.host_context,
                shutdown_event=self._deps.shutdown_event,
                handle_host_mode_request=handle_host_mode_request,
                handle_host_mode_notification=handle_host_mode_notification,
                publish_event=self._deps.event_publish,
                attempt_reconnection=self._deps.attempt_reconnection,
                track_background_task=self._deps.track_background_task,
            )
            connection.task_state.reader_task = create_ephemeral_task(
                stdio_reader(connection=connection, inbound=inbound),
            )

            async def _send_stdio(
                method_name: str,
                parameters: JSONDict,
            ) -> JSONValue | None:
                return await send_stdio_request(connection, method_name, parameters)

            if not await self._deps.negotiator.initialize_connection(connection, _send_stdio):
                await self._deps.cleanup_connection_resources(connection)
                return False
            return True
        except asyncio.CancelledError:
            await self._deps.cleanup_connection_resources(connection)
            raise
        except HTTP_RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._deps.logger,
                exception,
                message="stdio connection failed",
                operation=OPERATION,
                details={"server_name": connection.config.name},
            )
            connection.last_error = str(exception)
            await self._deps.cleanup_connection_resources(connection)
            return False

    async def connect_streamable_http(self, connection: MCPServerConnection) -> bool:
        protocol_ver = connection.protocol_version or self._deps.protocol_version
        inbound = MCPInboundReaderDependencies(
            host_context=self._deps.host_context,
            shutdown_event=self._deps.shutdown_event,
            handle_host_mode_request=handle_host_mode_request,
            handle_host_mode_notification=handle_host_mode_notification,
            publish_event=self._deps.event_publish,
            attempt_reconnection=self._deps.attempt_reconnection,
            track_background_task=self._deps.track_background_task,
        )
        try:

            async def _on_transport_auth_error(
                failed_connection: MCPServerConnection,
                status_code: int,
                www_authenticate: str | None,
            ) -> None:
                await persist_mcp_oauth_auth_error(
                    self._deps.db_mcp,
                    server_id=failed_connection.config.id,
                    status_code=status_code,
                    www_authenticate=www_authenticate,
                    auth_type=failed_connection.config.auth_type,
                )

            return await connect_streamable_http_transport(
                http_client=self._deps.http_client,
                connection=connection,
                get_headers=lambda ver: self._deps.build_http_headers(
                    connection.config,
                    ver or protocol_ver,
                ),
                runtime_flags=self._deps.runtime_flags,
                cleanup_connection_resources=self._deps.cleanup_connection_resources,
                on_transport_auth_error=_on_transport_auth_error,
                inbound=inbound,
                initialize_remote_connection=lambda sender: self._deps.negotiator.initialize_connection(
                    connection,
                    sender,
                ),
            )
        except MCPStreamableHTTPNotSupportedError:
            connection.last_error = "Streamable HTTP transport not supported by server."
            return False
