"""SoAI - MCP Streamable HTTP request helpers [backend/mcp/protocol/transport_stream_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING

import httpx2

from core.errors.exception_logging import log_exception
from core.errors.external_service_exception import ExternalServiceError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from mcp.protocol.connection_request_state import (
    cancel_pending_request,
    create_pending_request,
)
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.jsonrpc import (
    build_jsonrpc_notification,
    build_jsonrpc_request,
)
from mcp.protocol.streamable_http_response import (
    MCPStreamAuthorizationError,
    MCPStreamInsufficientScopeError,
    raise_for_streamable_http_send_status,
    resolve_streamable_http_response_message,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "send_stream_message",
    "send_stream_request",
)

LOGGER_NAME = "SoAI.mcp.protocol.transport_stream_requests"
OPERATION_MCP_PROTOCOL_SEND_STREAM_CANCEL = "mcp.protocol.send_stream_cancel"
OPERATION_MCP_PROTOCOL_SEND_STREAM_REQUEST = "mcp.protocol.send_stream_request"


async def send_stream_request(
    *,
    http_client: httpx2.AsyncClient,
    connection: MCPServerConnection,
    url: str,
    headers: Mapping[str, str],
    method: str,
    params: JSONDict,
) -> JSONValue | None:
    logger = get_logger(LOGGER_NAME)
    if http_client is None:
        raise ExternalServiceError("HTTP client not configured for MCP requests.")
    message_id, future = await create_pending_request(connection.request_state)
    request = build_jsonrpc_request(message_id, method, params)
    try:
        async with http_client.stream(
            "POST",
            url,
            json=request,
            headers={
                **dict(headers),
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            timeout=connection.config.timeout_sec,
        ) as response:
            status_code = response.status_code
            if status_code not in (200, 202):
                raise_for_streamable_http_send_status(response)
            await resolve_streamable_http_response_message(
                response=response,
                connection=connection,
                message_id=message_id,
                future=future,
            )
        return await asyncio.wait_for(future, timeout=connection.config.timeout_sec)
    except asyncio.CancelledError:
        await cancel_pending_request(connection.request_state, message_id)
        raise
    except (httpx2.TimeoutException, TimeoutError):
        await cancel_pending_request(connection.request_state, message_id)
        if method != "initialize":
            notification = build_jsonrpc_notification(
                "notifications/cancelled",
                {"rpcId": message_id, "reason": "Request timed out"},
            )
            try:
                await send_stream_message(
                    http_client=http_client,
                    connection=connection,
                    url=url,
                    headers=headers,
                    message=notification,
                )
            except HTTP_RECOVERABLE_EXCEPTIONS as notify_exception:
                log_exception(
                    logger,
                    notify_exception,
                    message="Failed to send cancellation notification",
                    operation=OPERATION_MCP_PROTOCOL_SEND_STREAM_CANCEL,
                    details={"method": method},
                    level="warning",
                )
        return None
    except (MCPStreamAuthorizationError, MCPStreamInsufficientScopeError):
        await cancel_pending_request(connection.request_state, message_id)
        raise
    except ExternalServiceError:
        await cancel_pending_request(connection.request_state, message_id)
        raise
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        await cancel_pending_request(connection.request_state, message_id)
        log_exception(
            logger,
            exception,
            message="Streamable HTTP request error",
            operation=OPERATION_MCP_PROTOCOL_SEND_STREAM_REQUEST,
            details={"method": method},
        )
        return None


async def send_stream_message(
    *,
    http_client: httpx2.AsyncClient,
    connection: MCPServerConnection,
    url: str,
    headers: Mapping[str, str],
    message: JSONDict,
) -> None:
    if http_client is None:
        raise ExternalServiceError("HTTP client not configured for MCP requests.")
    response = await http_client.post(
        url,
        json=message,
        headers={
            **dict(headers),
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        timeout=connection.config.timeout_sec,
    )
    raise_for_streamable_http_send_status(response)
