"""SoAI - MCP Streamable HTTP transport connect flow [backend/mcp/protocol/transport_streamable_http_connect.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import override

import httpx2

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_exception
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.mcp.mcp_2025_11_25 import MCP_SESSION_ID_HEADER
from core.runtime.network_policy import OfflineModeError, validate_local_only_url
from core.runtime.protocols import RuntimeFlagsViewProtocol
from core.types.json import JSONDict, JSONValue
from mcp.protocol.connection_request_state import (
    cancel_pending_request,
    create_pending_request,
)
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.inbound_reader_dependencies import MCPInboundReaderDependencies
from mcp.protocol.jsonrpc import build_jsonrpc_request
from mcp.protocol.streamable_http_response import (
    MCPStreamAuthorizationError,
    MCPStreamInsufficientScopeError,
    raise_for_streamable_http_auth_status,
    resolve_streamable_http_response_message,
)
from mcp.protocol.transport_streamable_http_reader import streamable_http_reader
from mcp.protocol.transport_streamable_http_send import send_streamable_http_request

__all__ = (
    "MCPStreamableHTTPNotSupportedError",
    "connect_streamable_http_transport",
)

LOGGER_NAME = "SoAI.mcp.protocol.transport_streamable_http_connect"
OPERATION_MCP_CONNECT_STREAMABLE_HTTP = "mcp.connect.streamable_http"


class MCPStreamableHTTPNotSupportedError(Exception):
    __slots__ = ("message", "status_code")

    def __init__(self, *, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = int(status_code)
        self.message = str(message)

    def __getnewargs_ex__(self) -> tuple[tuple[()], dict[str, int | str]]:
        return ((), {"status_code": self.status_code, "message": self.message})

    @override
    def __str__(self) -> str:
        return self.message


async def connect_streamable_http_transport(
    *,
    http_client: httpx2.AsyncClient,
    connection: MCPServerConnection,
    get_headers: Callable[[str | None], dict[str, str]],
    runtime_flags: RuntimeFlagsViewProtocol,
    cleanup_connection_resources: Callable[[MCPServerConnection], Awaitable[None]],
    on_transport_auth_error: Callable[[MCPServerConnection, int, str | None], Awaitable[None]],
    inbound: MCPInboundReaderDependencies,
    initialize_remote_connection: Callable[
        [Callable[[str, JSONDict], Awaitable[JSONValue | None]]],
        Awaitable[bool],
    ],
) -> bool:
    logger = get_logger(LOGGER_NAME)
    if http_client is None:
        logger.warning("HTTP client not available for MCP Streamable HTTP transport")
        connection.last_error = "HTTP client not configured"
        return False
    try:
        await validate_local_only_url(
            runtime_flags,
            connection.config.endpoint,
            source="MCP Streamable HTTP connection",
        )
        connection.session_id = None
        connection.last_event_id = None

        def _ensure_reader_running() -> None:
            if connection.task_state.reader_task and not connection.task_state.reader_task.done():
                return
            headers = get_headers(connection.protocol_version)
            if connection.session_id:
                headers[MCP_SESSION_ID_HEADER] = connection.session_id
            reader_task = create_ephemeral_task(
                streamable_http_reader(
                    http_client=http_client,
                    connection=connection,
                    url=connection.config.endpoint,
                    headers=headers,
                    inbound=inbound,
                    cleanup_connection_resources=cleanup_connection_resources,
                    on_transport_auth_error=on_transport_auth_error,
                ),
            )
            connection.task_state.reader_task = reader_task

        async def _send(method: str, params: JSONDict) -> JSONValue | None:
            if method == "initialize":
                return await _send_streamable_http_initialize(
                    http_client=http_client,
                    connection=connection,
                    get_headers=get_headers,
                    params=params,
                    ensure_reader_running=_ensure_reader_running,
                )
            _ensure_reader_running()
            return await send_streamable_http_request(
                http_client=http_client,
                connection=connection,
                get_headers=get_headers,
                method=method,
                params=params,
            )

        connected = await initialize_remote_connection(_send)
        if not connected:
            await cleanup_connection_resources(connection)
            return False
        _ensure_reader_running()
        return True
    except MCPStreamableHTTPNotSupportedError:
        await cleanup_connection_resources(connection)
        raise
    except (MCPStreamAuthorizationError, MCPStreamInsufficientScopeError):
        await cleanup_connection_resources(connection)
        raise
    except OfflineModeError as exception:
        connection.last_error = str(exception)
        await cleanup_connection_resources(connection)
        return False
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Streamable HTTP connection failed",
            operation=OPERATION_MCP_CONNECT_STREAMABLE_HTTP,
            details={"server_name": connection.config.name},
        )
        connection.last_error = str(exception)
        await cleanup_connection_resources(connection)
        return False


async def _send_streamable_http_initialize(
    *,
    http_client: httpx2.AsyncClient,
    connection: MCPServerConnection,
    get_headers: Callable[[str | None], dict[str, str]],
    params: JSONDict,
    ensure_reader_running: Callable[[], None],
) -> JSONValue | None:
    protocol_version_value = params.get("protocolVersion")
    protocol_version = (
        str(protocol_version_value)
        if isinstance(protocol_version_value, str) and protocol_version_value.strip()
        else connection.protocol_version
    )
    message_id, future = await create_pending_request(connection.request_state)
    message = build_jsonrpc_request(message_id, "initialize", params)
    headers = get_headers(protocol_version)
    headers = {
        header_name: header_value
        for header_name, header_value in headers.items()
        if header_name.lower() != MCP_SESSION_ID_HEADER
    }
    try:
        async with http_client.stream(
            "POST",
            connection.config.endpoint,
            headers={
                **headers,
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            json=message,
            timeout=connection.config.timeout_sec,
        ) as response:
            status = response.status_code
            if status in (400, 404, 405):
                await cancel_pending_request(connection.request_state, message_id)
                raise MCPStreamableHTTPNotSupportedError(
                    status_code=status,
                    message=f"Streamable HTTP initialize not supported (HTTP {status})",
                )
            if status in (401, 403):
                await cancel_pending_request(connection.request_state, message_id)
                raise_for_streamable_http_auth_status(
                    status,
                    response.headers.get("WWW-Authenticate"),
                )
            session_id_value = response.headers.get(MCP_SESSION_ID_HEADER)
            session_id = session_id_value.strip() if isinstance(session_id_value, str) else None
            if session_id:
                connection.session_id = session_id
            if status not in (200, 202):
                await cancel_pending_request(connection.request_state, message_id)
                connection.last_error = f"Streamable HTTP initialize HTTP {status}"
                return None
            await resolve_streamable_http_response_message(
                response=response,
                connection=connection,
                message_id=message_id,
                future=future,
            )
            if not future.done():
                ensure_reader_running()
            try:
                return await asyncio.wait_for(future, timeout=connection.config.timeout_sec)
            except TimeoutError:
                connection.last_error = "Streamable HTTP initialize timed out"
                await cancel_pending_request(connection.request_state, message_id)
                return None
    except httpx2.TimeoutException:
        connection.last_error = "Streamable HTTP initialize timed out"
        await cancel_pending_request(connection.request_state, message_id)
        return None
    except asyncio.CancelledError:
        await cancel_pending_request(connection.request_state, message_id)
        raise
    except HTTP_RECOVERABLE_EXCEPTIONS:
        await cancel_pending_request(connection.request_state, message_id)
        raise
