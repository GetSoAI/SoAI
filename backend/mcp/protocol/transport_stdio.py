"""SoAI - Model Context Protocol stdio transport [backend/mcp/protocol/transport_stdio.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_mcp import MCPServerDisconnectedEvent
from core.logging.trace import get_logger
from core.serialization.json import serialize_json_compact_stable_strict
from core.serialization.json_parsing import parse_json_value
from core.timing.constants import MODERATE_DELAY_SEC, RESPONSIVE_TIMEOUT_SEC
from mcp.protocol.connection_request_state import (
    cancel_pending_request,
    create_pending_request,
)
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.inbound_dispatch import dispatch_inbound_message_for_reader
from mcp.protocol.inbound_reader_dependencies import MCPInboundReaderDependencies
from mcp.protocol.internal_protocols import StdinDrainProtocol
from mcp.protocol.jsonrpc import build_jsonrpc_notification, build_jsonrpc_request
from mcp.protocol.types import MCPJSONRPCError, MCPServerStatus

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "send_stdio_message",
    "send_stdio_request",
    "stdio_reader",
)

LOGGER_NAME = "SoAI.mcp.protocol.transport_stdio"
OPERATION_MCP_PROTOCOL_STDIO_READER = "mcp.protocol.stdio_reader"
OPERATION_MCP_TRANSPORT_STDIO_SEND_JSONRPC_REQUEST = "mcp.transport_stdio.send_jsonrpc_request"
OPERATION_MCP_TRANSPORT_STDIO_SEND_JSONRPC_REQUEST_CANCELLATION_NOTIFY = (
    "mcp.transport_stdio.send_jsonrpc_request.cancellation_notify"
)
OPERATION_MCP_TRANSPORT_STDIO_SEND_JSONRPC_REQUEST_TIMEOUT_NOTIFY = (
    "mcp.transport_stdio.send_jsonrpc_request.timeout_notify"
)

STDIN_DRAIN_EXCEPTIONS: tuple[type[BaseException], ...] = (TimeoutError, *RECOVERABLE_EXCEPTIONS)


async def _cancel_stdin_drain_task(drain_task: asyncio.Task[None]) -> None:
    drain_task.cancel()
    results = await asyncio.gather(drain_task, return_exceptions=True)
    drain_result = results[0]
    if isinstance(drain_result, RECOVERABLE_EXCEPTIONS):
        log_handled_exception(
            get_logger(LOGGER_NAME),
            drain_result,
            message="MCP stdin drain cleanup failed (non-critical).",
            operation=OPERATION_MCP_TRANSPORT_STDIO_SEND_JSONRPC_REQUEST,
            level="debug",
        )


async def _drain_stdin_with_timeout(stdin_ref: StdinDrainProtocol, *, timeout_sec: float) -> None:
    drain_task = create_ephemeral_task(
        stdin_ref.drain(),
        name="mcp.protocol.transport_stdio.drain_stdin",
        log_exceptions=False,
    )
    drain_exception: BaseException | None = None
    try:
        await asyncio.wait_for(drain_task, timeout=timeout_sec)
    except asyncio.CancelledError as exception:
        drain_exception = exception
    except STDIN_DRAIN_EXCEPTIONS as exception:
        drain_exception = exception
    if drain_exception is not None:
        await _cancel_stdin_drain_task(drain_task)
        raise drain_exception


async def send_stdio_message(connection: MCPServerConnection, message: JSONDict) -> None:
    if connection.process and connection.process.stdin:
        payload = serialize_json_compact_stable_strict(message)
        if "\n" in payload or "\r" in payload:
            raise MCPJSONRPCError(-32600, "Response contains invalid newline characters")
        async with connection.io_lock:
            async with connection.request_state.lock:
                connection.process.stdin.write((f"{payload}\n").encode())
                stdin_ref = connection.process.stdin
            await _drain_stdin_with_timeout(stdin_ref, timeout_sec=RESPONSIVE_TIMEOUT_SEC)


async def send_stdio_request(
    connection: MCPServerConnection,
    method: str,
    params: JSONDict,
) -> JSONValue | None:
    logger = get_logger(LOGGER_NAME)
    message_id, future = await create_pending_request(connection.request_state)
    request = build_jsonrpc_request(message_id, method, params)
    cancelled = False
    try:
        async with connection.io_lock:
            stdin_ref: StdinDrainProtocol | None = None
            cleanup_and_return = False
            invalid_payload = False
            async with connection.request_state.lock:
                if not connection.process or not connection.process.stdin:
                    cleanup_and_return = True
                else:
                    payload_text = serialize_json_compact_stable_strict(request)
                    if "\n" in payload_text or "\r" in payload_text:
                        invalid_payload = True
                    else:
                        connection.process.stdin.write((f"{payload_text}\n").encode())
                        stdin_ref = connection.process.stdin
            if cleanup_and_return:
                await cancel_pending_request(connection.request_state, message_id)
                return None
            if invalid_payload:
                await cancel_pending_request(connection.request_state, message_id)
                raise MCPJSONRPCError(-32600, "Request contains invalid newline characters")
            if stdin_ref is None:
                await cancel_pending_request(connection.request_state, message_id)
                return None
            try:
                await _drain_stdin_with_timeout(stdin_ref, timeout_sec=RESPONSIVE_TIMEOUT_SEC)
            except RECOVERABLE_EXCEPTIONS as exception:
                await cancel_pending_request(connection.request_state, message_id)
                log_exception(
                    logger,
                    exception,
                    message="MCP request drain failed",
                    operation=OPERATION_MCP_TRANSPORT_STDIO_SEND_JSONRPC_REQUEST,
                    details={"method": method, "message_id": message_id},
                    level="warning",
                )
                return None
        return await asyncio.wait_for(future, timeout=connection.config.timeout_sec)
    except asyncio.CancelledError:
        cancelled = True
    except TimeoutError:
        await cancel_pending_request(connection.request_state, message_id)
        if method != "initialize":
            reason = "Request timed out"
            notification = build_jsonrpc_notification(
                "notifications/cancelled",
                {"rpcId": message_id, "reason": reason},
            )
            try:
                await send_stdio_message(connection, notification)
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to send timeout notification (non-critical).",
                    operation=OPERATION_MCP_TRANSPORT_STDIO_SEND_JSONRPC_REQUEST_TIMEOUT_NOTIFY,
                    details={"method": method, "message_id": message_id},
                    level="debug",
                )
        logger.warning("MCP request timed out: %s", method)
        return None
    except HANDLED_RUNTIME_EXCEPTIONS:
        await cancel_pending_request(connection.request_state, message_id)
        raise
    if cancelled:
        await cancel_pending_request(connection.request_state, message_id)
        if method != "initialize":
            notification = build_jsonrpc_notification(
                "notifications/cancelled",
                {"rpcId": message_id, "reason": "Request cancelled by client"},
            )
            try:
                await send_stdio_message(connection, notification)
            except RECOVERABLE_EXCEPTIONS as exception:
                log_handled_exception(
                    logger,
                    exception,
                    message="Failed to send cancellation notification (non-critical).",
                    operation=(
                        OPERATION_MCP_TRANSPORT_STDIO_SEND_JSONRPC_REQUEST_CANCELLATION_NOTIFY
                    ),
                    details={"method": method, "message_id": message_id},
                    level="debug",
                )
        logger.warning("MCP request cancelled: %s", method)
        raise asyncio.CancelledError
    return None


async def stdio_reader(
    *,
    connection: MCPServerConnection,
    inbound: MCPInboundReaderDependencies,
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        while (
            connection.process
            and connection.process.returncode is None
            and connection.process.stdout
        ):
            try:
                line = await asyncio.wait_for(
                    connection.process.stdout.readline(),
                    timeout=MODERATE_DELAY_SEC,
                )
            except TimeoutError:
                if inbound.shutdown_event.is_set():
                    break
                continue
            if not line:
                break
            try:
                content = line.decode().rstrip("\n\r")
                if "\n" in content or "\r" in content:
                    logger.warning(
                        "Invalid MCP message with embedded newlines from server: %s",
                        connection.config.name,
                    )
                    continue
                message_raw = parse_json_value(content)
                if not isinstance(message_raw, dict):
                    logger.warning(
                        "Invalid MCP message payload type from server %s: %s",
                        connection.config.name,
                        type(message_raw).__name__,
                    )
                    continue
                await dispatch_inbound_message_for_reader(
                    message=message_raw,
                    inbound=inbound,
                    connection=connection,
                    logger=logger,
                    operation="mcp.protocol.stdio_reader.dispatch_inbound_message",
                    error_message="Unhandled exception while dispatching stdio inbound message",
                    error_details={"server_name": connection.config.name},
                )
            except UnicodeDecodeError:
                logger.warning("Invalid UTF-8 from MCP server: %s", line[:100])
            except ValidationError:
                logger.warning("Invalid JSON from MCP server: %s", line[:100])
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Error in stdio reader",
            operation=OPERATION_MCP_PROTOCOL_STDIO_READER,
            details={"server_name": connection.config.name},
        )
    if (
        inbound.shutdown_event.is_set()
        or not connection.task_state.initialized
        or (not connection.config.auto_reconnect)
        or connection.task_state.user_disconnected
    ):
        return
    if connection.status == MCPServerStatus.CONNECTED:
        connection.status = MCPServerStatus.DISCONNECTED
        await inbound.publish_event(
            MCPServerDisconnectedEvent(server_id=connection.config.id, reason="Connection lost"),
        )
        logger.warning(
            "MCP server %s connection lost, scheduling reconnection",
            connection.config.name,
        )
    reconnect_task = connection.task_state.reconnect_task
    if not reconnect_task or reconnect_task.done():

        async def _reconnect() -> None:
            await inbound.attempt_reconnection(connection)

        reconnect_runner = create_ephemeral_task(_reconnect())
        connection.task_state.reconnect_task = reconnect_runner
        inbound.track_background_task(reconnect_runner)
