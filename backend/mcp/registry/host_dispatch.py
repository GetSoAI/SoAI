"""SoAI - MCP host-mode request and notification dispatcher [backend/mcp/registry/host_dispatch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_mcp import (
    MCPPromptsListChangedEvent,
    MCPResourcesListChangedEvent,
    MCPToolsListChangedEvent,
)
from core.logging.trace import get_logger
from core.mcp.jsonrpc_messages import resolve_jsonrpc_params_object
from core.mcp.jsonrpc_responses import build_error_response, build_success_response
from core.mcp.mcp_2025_11_25 import JSON_RPC_VERSION, validate_jsonrpc_id
from core.mcp.protocols_runtime import MCPRemoteHostProtocol
from mcp.host.internal_protocols import (
    MCPHostContextProtocol,
    MCPServerHostProtocol,
)
from mcp.protocol.connection_state import MCPServerConnection
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.elicitation import handle_host_elicitation_create
from mcp.registry.handler_maps import resolve_task_method_handler
from mcp.registry.sampling import handle_host_sampling_create_message

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "dispatch_host_mode_method",
    "handle_host_mode_notification",
    "handle_host_mode_request",
    "handle_list_changed_async",
)

LOGGER_NAME = "SoAI.mcp.registry.host_dispatch"
OPERATION_MCP_HOST_NOTIFICATIONS_LIST_CHANGED = "mcp.host.notifications.list_changed"
OPERATION_MCP_HOST_REQUEST = "mcp.host.request"


def _resolve_list_changed_notification_handler(
    method: str,
) -> tuple[str, str, type[Event]] | None:
    if method == "notifications/tools/list_changed":
        return ("tools/list", "tools", MCPToolsListChangedEvent)
    if method == "notifications/resources/list_changed":
        return ("resources/list", "resources", MCPResourcesListChangedEvent)
    if method == "notifications/prompts/list_changed":
        return ("prompts/list", "prompts", MCPPromptsListChangedEvent)
    return None


async def dispatch_host_mode_method(
    remote: MCPRemoteHostProtocol,
    server: MCPServerHostProtocol,
    method: str,
    parameters: JSONDict,
    server_id: str,
) -> JSONValue:
    if method == "roots/list":
        return {"roots": remote.normalize_roots()}
    if method == "sampling/createMessage":
        return await handle_host_sampling_create_message(remote, server, parameters, server_id)
    if method == "elicitation/create":
        return await handle_host_elicitation_create(remote, server, parameters, server_id)
    task_handler = resolve_task_method_handler(method)
    if task_handler is not None:
        return await task_handler(server, parameters, server_id)
    raise MCPJSONRPCError(-32601, f"Method not found: {method}")


async def handle_host_mode_request(
    host_context: MCPHostContextProtocol,
    connection: MCPServerConnection,
    request: JSONDict,
) -> None:
    logger = get_logger(LOGGER_NAME)
    remote = host_context
    server = host_context.server
    server_id = connection.config.id
    rpc_id_raw = request.get("id")
    if rpc_id_raw is not None and (
        not isinstance(rpc_id_raw, str | int) or isinstance(rpc_id_raw, bool)
    ):
        await remote.send_host_mode_message(
            server_id,
            build_error_response(
                None,
                -32600,
                f"Invalid JSON-RPC id type: {type(rpc_id_raw).__name__}",
            ),
        )
        return
    is_id_valid, rpc_id = validate_jsonrpc_id(rpc_id_raw)
    if not is_id_valid:
        await remote.send_host_mode_message(
            server_id,
            build_error_response(
                None,
                -32600,
                f"Invalid JSON-RPC id type: {type(rpc_id_raw).__name__}",
            ),
        )
        return
    if server is None:
        await remote.send_host_mode_message(
            server_id,
            build_error_response(rpc_id, -32603, "Host server is not configured"),
        )
        return
    if request.get("jsonrpc") != JSON_RPC_VERSION:
        await remote.send_host_mode_message(
            server_id,
            build_error_response(rpc_id, -32600, "Invalid JSON-RPC version"),
        )
        return
    method_value = request.get("method")
    if (
        not isinstance(method_value, str)
        or not method_value
        or method_value != method_value.strip()
    ):
        await remote.send_host_mode_message(
            server_id,
            build_error_response(rpc_id, -32600, "Missing method"),
        )
        return
    method = method_value
    try:
        parameters = resolve_jsonrpc_params_object(request.get("params", {}))
    except ValidationError as exception:
        await remote.send_host_mode_message(
            server_id,
            build_error_response(rpc_id, -32602, str(exception)),
        )
        return
    try:
        result = await dispatch_host_mode_method(
            remote,
            server,
            method,
            parameters,
            server_id,
        )
        await remote.send_host_mode_message(server_id, build_success_response(rpc_id, result))
    except MCPJSONRPCError as exception:
        await remote.send_host_mode_message(
            server_id,
            build_error_response(rpc_id, exception.rpc_code, exception.message, exception.data),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Unhandled error in host mode request handler",
            operation=OPERATION_MCP_HOST_REQUEST,
            details={"method": method, "server_name": connection.config.name},
        )
        await remote.send_host_mode_message(
            server_id,
            build_error_response(rpc_id, -32603, "Internal error"),
        )


async def handle_list_changed_async(
    remote: MCPRemoteHostProtocol,
    connection: MCPServerConnection,
    method: str,
    request_method: str,
    response_key: str,
    event_class: type[Event],
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        response = await remote.send_host_mode_request(connection.config.id, request_method, {})
        if isinstance(response, dict):
            response_value = response.get(response_key)
            if isinstance(response_value, list):
                normalized_list: list[JSONDict] = [
                    item for item in response_value if isinstance(item, dict)
                ]
                match response_key:
                    case "tools":
                        connection.tools = normalized_list
                    case "resources":
                        connection.resources = normalized_list
                    case "prompts":
                        connection.prompts = normalized_list
                    case _:
                        logger.warning(
                            "Unexpected list-changed response key %s for method %s (server=%s).",
                            response_key,
                            method,
                            connection.config.name,
                        )
        await remote.event_bus.publish(event_class())
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Error handling list changed notification",
            operation=OPERATION_MCP_HOST_NOTIFICATIONS_LIST_CHANGED,
            details={"method": method, "server_name": connection.config.name},
            level="warning",
        )


async def handle_host_mode_notification(
    host_context: MCPHostContextProtocol,
    connection: MCPServerConnection,
    notification: JSONDict,
) -> None:
    logger = get_logger(LOGGER_NAME)
    remote = host_context
    server = host_context.server
    method = str(notification.get("method", "") or "")
    parameters_raw = notification.get("params", {}) or {}
    if not isinstance(parameters_raw, dict):
        logger.warning(
            "Host mode notification params must be an object; got %s for method %s (server=%s).",
            type(parameters_raw).__name__,
            method,
            connection.config.name,
        )
        return
    parameters = parameters_raw
    if server is None:
        logger.warning(
            "Host mode notification ignored because server context is missing: %s",
            method,
        )
        return
    list_changed_handler = _resolve_list_changed_notification_handler(method)
    if list_changed_handler is not None:
        request_method, response_key, event_class = list_changed_handler
        _ = remote.schedule_background_task(
            handle_list_changed_async(
                remote=remote,
                connection=connection,
                method=method,
                request_method=request_method,
                response_key=response_key,
                event_class=event_class,
            ),
            name=f"mcp-host-list-changed:{connection.config.id}:{response_key}",
        )
        return
    if method == "notifications/message":
        level_name = str(parameters.get("level", "info")).upper()
        logger_level = logging.INFO
        match level_name:
            case "TRACE":
                logger_level = logging.DEBUG
            case "DEBUG":
                logger_level = logging.DEBUG
            case "INFO":
                logger_level = logging.INFO
            case "WARN" | "WARNING":
                logger_level = logging.WARNING
            case "ERROR":
                logger_level = logging.ERROR
            case "CRITICAL" | "FATAL":
                logger_level = logging.CRITICAL
            case _:
                logger_level = logging.INFO
        logger.log(
            logger_level,
            "MCP server %s: %s",
            connection.config.name,
            parameters.get("data", ""),
        )
        return
    if method == "notifications/elicitation/complete":
        elicitation_id = parameters.get("elicitationId")
        if elicitation_id and isinstance(elicitation_id, str):
            if await remote.clear_pending_url_elicitation(connection.config.id, elicitation_id):
                await server.notification.emit_notification(connection.config.id, notification)
