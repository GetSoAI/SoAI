"""SoAI - MCP inbound message dispatch helpers [backend/mcp/protocol/inbound_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import StandardLogger
from mcp.host.internal_protocols import MCPHostContextProtocol
from mcp.protocol.connection_request_state import pop_pending_request
from mcp.protocol.jsonrpc import (
    coerce_jsonrpc_id_to_int_for_lookup,
    resolve_pending_response,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.protocol.connection_state import MCPServerConnection
    from mcp.protocol.inbound_reader_dependencies import MCPInboundReaderDependencies

__all__ = (
    "dispatch_inbound_message",
    "dispatch_inbound_message_for_reader",
    "dispatch_inbound_message_with_isolation",
)

OPERATION_MCP_PROTOCOL_INBOUND_DISPATCH_DISPATCH_INBOUND_MESSAGE_WITH_ISOLATION = (
    "mcp.protocol.inbound_dispatch.dispatch_inbound_message_with_isolation"
)


async def dispatch_inbound_message(
    *,
    message: JSONDict,
    host_context: MCPHostContextProtocol,
    connection: MCPServerConnection,
    handle_host_mode_request: Callable[
        [MCPHostContextProtocol, MCPServerConnection, JSONDict],
        Awaitable[None],
    ],
    handle_host_mode_notification: Callable[
        [MCPHostContextProtocol, MCPServerConnection, JSONDict],
        Awaitable[None],
    ],
) -> None:
    if "method" in message and "id" in message:
        await handle_host_mode_request(host_context, connection, message)
        return
    if "method" in message:
        await handle_host_mode_notification(host_context, connection, message)
        return
    if message.get("id") is None:
        return
    normalized_id = coerce_jsonrpc_id_to_int_for_lookup(message.get("id"))
    if normalized_id is None:
        return
    future = await pop_pending_request(connection.request_state, normalized_id)
    if future is not None:
        resolve_pending_response(future, message)


async def dispatch_inbound_message_with_isolation(
    *,
    message: JSONDict,
    host_context: MCPHostContextProtocol,
    connection: MCPServerConnection,
    handle_host_mode_request: Callable[
        [MCPHostContextProtocol, MCPServerConnection, JSONDict],
        Awaitable[None],
    ],
    handle_host_mode_notification: Callable[
        [MCPHostContextProtocol, MCPServerConnection, JSONDict],
        Awaitable[None],
    ],
    logger: StandardLogger,
    operation: str,
    error_message: str,
    error_details: JSONDict,
) -> None:
    try:
        await dispatch_inbound_message(
            message=message,
            host_context=host_context,
            connection=connection,
            handle_host_mode_request=handle_host_mode_request,
            handle_host_mode_notification=handle_host_mode_notification,
        )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            logger,
            coerced,
            message=error_message,
            operation=OPERATION_MCP_PROTOCOL_INBOUND_DISPATCH_DISPATCH_INBOUND_MESSAGE_WITH_ISOLATION,
            details=error_details,
            level="warning",
        )


async def dispatch_inbound_message_for_reader(
    *,
    message: JSONDict,
    inbound: MCPInboundReaderDependencies,
    connection: MCPServerConnection,
    logger: StandardLogger,
    operation: str,
    error_message: str,
    error_details: JSONDict,
) -> None:
    await dispatch_inbound_message_with_isolation(
        message=message,
        host_context=inbound.host_context,
        connection=connection,
        handle_host_mode_request=inbound.handle_host_mode_request,
        handle_host_mode_notification=inbound.handle_host_mode_notification,
        logger=logger,
        operation=operation,
        error_message=error_message,
        error_details=error_details,
    )
