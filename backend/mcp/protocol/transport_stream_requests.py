"""SoAI - MCP Streamable HTTP request helpers [backend/mcp/protocol/transport_stream_requests.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING

import httpx2

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_logging import log_exception
from core.errors.external_service_exception import ExternalServiceError
from core.errors.http_recoverable import HTTP_RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from mcp.protocol.connection_request_state import (
    cancel_pending_request,
    create_outbound_request,
)
from mcp.protocol.connection_state import MCPServerConnection
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
    outbound = await create_outbound_request(
        connection.request_state,
        method=method,
        params=params,
        send_notification=partial(
            send_stream_message,
            http_client=http_client,
            connection=connection,
            url=url,
            headers=headers,
        ),
    )

    async def cancel_request(reason: str) -> None:
        try:
            await outbound.cancel(reason)
        except HTTP_RECOVERABLE_EXCEPTIONS as notify_exception:
            log_exception(
                logger,
                notify_exception,
                message="Failed to send cancellation notification (non-critical).",
                operation=OPERATION_MCP_PROTOCOL_SEND_STREAM_CANCEL,
                details={"method": method},
                level="debug",
            )

    try:
        async with http_client.stream(
            "POST",
            url,
            json=outbound.message,
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
                message_id=outbound.message_id,
                future=outbound.future,
            )
        return await asyncio.wait_for(outbound.future, timeout=connection.config.timeout_sec)
    except asyncio.CancelledError:
        await uncancel_then_cleanup(cancel_request("Request cancelled by client"))
        raise
    except (httpx2.TimeoutException, TimeoutError):
        await uncancel_then_cleanup(
            cancel_request("Request timed out"),
            propagate_cancellation=True,
        )
        return None
    except (MCPStreamAuthorizationError, MCPStreamInsufficientScopeError):
        await cancel_pending_request(connection.request_state, outbound.message_id)
        raise
    except ExternalServiceError:
        await cancel_pending_request(connection.request_state, outbound.message_id)
        raise
    except HTTP_RECOVERABLE_EXCEPTIONS as exception:
        await cancel_pending_request(connection.request_state, outbound.message_id)
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
