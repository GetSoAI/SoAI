"""SoAI - MCP Streamable HTTP transport reader (client) [backend/mcp/protocol/transport_streamable_http_reader.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx2

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.serialization.json_parsing import parse_json_value
from core.streaming.sse_events import iter_sse_events
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from mcp.protocol.connection_request_state import cancel_all_pending_requests
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.inbound_dispatch import dispatch_inbound_message_for_reader
from mcp.protocol.inbound_reader_dependencies import MCPInboundReaderDependencies
from mcp.protocol.types import MCPServerStatus

__all__ = ("streamable_http_reader",)

LOGGER_NAME = "SoAI.mcp.protocol.transport_streamable_http_reader"
OPERATION_MCP_CONNECT_STREAMABLE_HTTP = "mcp.connect.streamable_http"


async def _cleanup_connection_without_self_cancel(
    *,
    connection: MCPServerConnection,
    cleanup_connection_resources: Callable[[MCPServerConnection], Awaitable[None]],
) -> None:
    current_task = asyncio.current_task()
    if current_task is not None and connection.task_state.reader_task is current_task:
        connection.task_state.reader_task = None
    await cleanup_connection_resources(connection)


async def streamable_http_reader(
    *,
    http_client: httpx2.AsyncClient,
    connection: MCPServerConnection,
    url: str,
    headers: dict[str, str],
    inbound: MCPInboundReaderDependencies,
    cleanup_connection_resources: Callable[[MCPServerConnection], Awaitable[None]],
    on_transport_auth_error: Callable[[MCPServerConnection, int, str | None], Awaitable[None]],
) -> None:
    logger = get_logger(LOGGER_NAME)
    if http_client is None:
        connection.last_error = "HTTP client not configured"
        return
    while True:
        if inbound.shutdown_event.is_set():
            return
        async with connection.request_state.lock:
            if connection.task_state.user_disconnected:
                return
        try:
            request_headers = dict(headers)
            if connection.last_event_id:
                request_headers["Last-Event-ID"] = connection.last_event_id
            async with http_client.stream(
                "GET",
                url,
                headers={
                    **request_headers,
                    "Accept": "text/event-stream",
                },
                timeout=None,
            ) as response:
                response.raise_for_status()
                async for sse in iter_sse_events(response.aiter_lines()):
                    if inbound.shutdown_event.is_set():
                        return
                    if sse.event_id:
                        connection.last_event_id = sse.event_id
                    if sse.event != "message" or not sse.data:
                        continue
                    try:
                        message_raw = parse_json_value(sse.data)
                    except (ValidationError, TypeError):
                        logger.warning("Invalid Streamable HTTP SSE message: %s", sse.data[:100])
                        continue
                    if not isinstance(message_raw, dict):
                        continue
                    await dispatch_inbound_message_for_reader(
                        message=message_raw,
                        inbound=inbound,
                        connection=connection,
                        logger=logger,
                        operation="mcp.streamable_http.reader.dispatch_inbound_message",
                        error_message="Unhandled exception while dispatching Streamable HTTP message",
                        error_details={
                            "endpoint": connection.config.endpoint,
                            "server_id": connection.config.id,
                        },
                    )
        except asyncio.CancelledError:
            return
        except httpx2.HTTPStatusError as exception:
            if exception.response.status_code == 405:
                return
            if exception.response.status_code in (401, 403):
                status_code = int(exception.response.status_code)
                www_authenticate = exception.response.headers.get("WWW-Authenticate")
                connection.last_error = f"Streamable HTTP authorization failed (HTTP {status_code})"
                connection.status = MCPServerStatus.AUTH_REQUIRED
                await cancel_all_pending_requests(connection.request_state)
                await _cleanup_connection_without_self_cancel(
                    connection=connection,
                    cleanup_connection_resources=cleanup_connection_resources,
                )
                await on_transport_auth_error(connection, status_code, www_authenticate)
                return
            if exception.response.status_code == 404:
                connection.last_error = "Streamable HTTP session terminated (HTTP 404)"
                await cancel_all_pending_requests(connection.request_state)
                await _cleanup_connection_without_self_cancel(
                    connection=connection,
                    cleanup_connection_resources=cleanup_connection_resources,
                )
                if connection.config.auto_reconnect and not connection.task_state.user_disconnected:
                    reconnect_task = connection.task_state.reconnect_task
                    if not reconnect_task or reconnect_task.done():

                        async def run_reconnect() -> None:
                            await inbound.attempt_reconnection(connection)

                        reconnect_runner = create_ephemeral_task(run_reconnect())
                        connection.task_state.reconnect_task = reconnect_runner
                        inbound.track_background_task(reconnect_runner)
                return
            connection.last_error = f"Streamable HTTP GET HTTP {exception.response.status_code}"
        except HTTP_RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Error in Streamable HTTP reader",
                operation=OPERATION_MCP_CONNECT_STREAMABLE_HTTP,
                details={
                    "endpoint": connection.config.endpoint,
                    "server_id": connection.config.id,
                },
                level="warning",
            )
            connection.last_error = str(exception)
        if inbound.shutdown_event.is_set():
            return
        if connection.config.auto_reconnect and not connection.task_state.user_disconnected:
            await asyncio.sleep(LOCAL_IO_TIMEOUT_SEC)
            continue
        if connection.status == MCPServerStatus.CONNECTED:
            connection.status = MCPServerStatus.DISCONNECTED
        return
