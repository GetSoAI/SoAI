"""SoAI - MCP resource registration and request routing handlers [backend/mcp/registry/resources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.mcp.argument_validation import require_non_empty_string_value
from core.mcp.content_envelopes import (
    build_json_resource_content,
    build_resource_contents_result,
)
from core.mcp.protocols_main import MCPServerProtocol
from core.metrics.keyspace_paths_mcp_server import (
    MCP_SERVER_COUNTER_RESOURCES_READS_FAILED,
    MCP_SERVER_COUNTER_RESOURCES_READS_SUCCEEDED,
    MCP_SERVER_COUNTER_RESOURCES_READS_TOTAL,
    MCP_SERVER_COUNTER_RESOURCES_SUBSCRIPTIONS,
    MCP_SERVER_COUNTER_RESOURCES_UNSUBSCRIPTIONS,
    MCP_SERVER_TIMING_RESOURCE_READ_MS,
)
from core.timing.epoch import epoch_seconds_float
from core.timing.monotonic import monotonic_ms
from mcp.protocol.catalog import build_resource_metadata, build_resource_templates
from mcp.protocol.types import MCPJSONRPCError, MCPServerStatus
from mcp.registry.internal_protocols import MCPRegistryManagerProtocol
from mcp.registry.special_resource_reads import try_read_special_resource

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "handle_resource_templates_list",
    "handle_resources_list",
    "handle_resources_read",
    "handle_resources_subscribe",
    "handle_resources_unsubscribe",
    "make_resource_models",
    "make_resource_plugins",
    "make_resource_system_status",
)

LOGGER_NAME = "SoAI.mcp.registry.resources"


def make_resource_models(
    manager: MCPServerProtocol,
) -> Callable[[], Awaitable[JSONDict]]:

    async def handler() -> JSONDict:
        info_service = manager.model_information_service
        models = await info_service.model_get_available() if info_service else []
        return build_json_resource_content(uri="soai://models", payload=models)

    return handler


def make_resource_plugins(
    manager: MCPServerProtocol,
) -> Callable[[], Awaitable[JSONDict]]:

    async def handler() -> JSONDict:
        plugins = await manager.database_plugins.get_all_listable_plugins()
        return build_json_resource_content(uri="soai://plugins", payload=plugins)

    return handler


def make_resource_system_status(
    manager: MCPServerProtocol,
) -> Callable[[], Awaitable[JSONDict]]:

    async def handler() -> JSONDict:
        return build_json_resource_content(
            uri="soai://system_status",
            payload={
                "status": "running",
                "mcp_enabled": bool(manager.enabled),
                "timestamp": epoch_seconds_float(),
            },
        )

    return handler


async def handle_resources_list(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
) -> JSONDict:
    resources: list[JSONDict] = []
    metadata_by_uri = build_resource_metadata()
    for uri in manager.registered_resources:
        metadata_value = metadata_by_uri.get(uri)
        metadata = metadata_value if isinstance(metadata_value, dict) else {}
        resources.append(
            {
                key: value
                for key, value in {
                    "uri": uri,
                    "name": metadata.get("name", uri),
                    "mimeType": metadata.get("mimeType", "application/json"),
                    "title": metadata.get("title"),
                    "description": metadata.get("description"),
                    "annotations": metadata.get("annotations"),
                    "icons": metadata.get("icons"),
                }.items()
                if value is not None
            },
        )
    async with manager.connection_registry.connections_lock:
        for connection in manager.connection_registry.connections.values():
            if connection.status != MCPServerStatus.CONNECTED:
                continue
            server_id = connection.config.id
            for resource in connection.resources:
                if not isinstance(resource, dict):
                    continue
                resources.append(
                    {
                        key: value
                        for key, value in {
                            "uri": f"{server_id}:{resource.get('uri', '')}",
                            "name": resource.get("name"),
                            "mimeType": resource.get("mimeType", "application/json"),
                            "title": resource.get("title"),
                            "description": resource.get("description"),
                            "annotations": resource.get("annotations"),
                            "icons": resource.get("icons"),
                        }.items()
                        if value is not None
                    },
                )
    cursor_value = parameters.get("cursor")
    cursor = cursor_value if isinstance(cursor_value, str) else None
    page, next_cursor = manager.pagination.paginate_list(resources, cursor)
    return {"resources": page, **({"nextCursor": next_cursor} if next_cursor else {})}


async def _try_route_to_remote_server_resource(
    manager: MCPRegistryManagerProtocol,
    uri: str,
    _: float,
) -> JSONDict | None:
    if ":" not in uri or uri in manager.registered_resources:
        return None
    potential_server_id, actual_uri = uri.split(":", 1)
    async with manager.connection_registry.connections_lock:
        connection = manager.connection_registry.connections.get(potential_server_id)
    if not connection or connection.status != MCPServerStatus.CONNECTED:
        return None
    result = await manager.host_mode.send_host_mode_request(
        connection.config.id,
        "resources/read",
        {"uri": actual_uri},
    )
    if result is None:
        manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_RESOURCES_READS_FAILED)
        raise MCPJSONRPCError(-32603, f"No response from server {potential_server_id}")
    if not isinstance(result, dict):
        manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_RESOURCES_READS_FAILED)
        result_type = type(result).__name__
        raise MCPJSONRPCError(
            -32603,
            (
                f"Invalid response from server {potential_server_id}: expected object, "
                f"got {result_type}"
            ),
        )
    manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_RESOURCES_READS_SUCCEEDED)
    return result


async def handle_resources_read(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
    client_id: str | None = None,
) -> JSONDict:
    manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_RESOURCES_READS_TOTAL)
    start_time_ms = monotonic_ms()
    token = manager.context.set_active_client_context(client_id)
    try:
        uri = require_non_empty_string_value(
            manager.registration.get_argument(parameters, "uri"),
            build_error=lambda message: MCPJSONRPCError(-32602, message),
            type_message="Invalid uri parameter (expected non-empty string)",
            empty_message="Invalid uri parameter (expected non-empty string)",
        )
        remote_result = await _try_route_to_remote_server_resource(manager, uri, time.monotonic())
        if remote_result is not None:
            return remote_result
        if uri in manager.registered_resources:
            return build_resource_contents_result(await manager.registered_resources[uri]())
        special_result = await try_read_special_resource(manager, uri)
        if special_result is not None:
            return special_result
        manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_RESOURCES_READS_FAILED)
        raise MCPJSONRPCError(-32602, f"Unknown resource: {uri}")
    except MCPJSONRPCError:
        raise
    except RECOVERABLE_EXCEPTIONS:
        manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_RESOURCES_READS_FAILED)
        raise
    finally:
        manager.context.reset_active_client_context(token)
        manager.metrics_manager.record_timing(
            *MCP_SERVER_TIMING_RESOURCE_READ_MS,
            duration_ms=float(monotonic_ms() - start_time_ms),
        )


async def handle_resources_subscribe(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
    client_id: str,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    uri = require_non_empty_string_value(
        parameters.get("uri"),
        build_error=lambda message: MCPJSONRPCError(-32602, message),
        type_message="Invalid uri parameter (expected non-empty string)",
        empty_message="Invalid uri parameter (expected non-empty string)",
    )
    session_id = manager.session.resolve_session_id(client_id)
    async with manager.resource_subscriptions_lock:
        if session_id not in manager.resource_subscriptions:
            manager.resource_subscriptions[session_id] = set()
        manager.resource_subscriptions[session_id].add(uri)
    manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_RESOURCES_SUBSCRIPTIONS)
    logger.debug("Session %s subscribed to resource: %s", session_id, uri)
    return {}


async def handle_resources_unsubscribe(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
    client_id: str,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    uri = require_non_empty_string_value(
        parameters.get("uri"),
        build_error=lambda message: MCPJSONRPCError(-32602, message),
        type_message="Invalid uri parameter (expected non-empty string)",
        empty_message="Invalid uri parameter (expected non-empty string)",
    )
    session_id = manager.session.resolve_session_id(client_id)
    async with manager.resource_subscriptions_lock:
        if session_id in manager.resource_subscriptions:
            manager.resource_subscriptions[session_id].discard(uri)
    manager.metrics_manager.increment_counter(*MCP_SERVER_COUNTER_RESOURCES_UNSUBSCRIPTIONS)
    logger.debug("Session %s unsubscribed from resource: %s", session_id, uri)
    return {}


async def handle_resource_templates_list(
    manager: MCPRegistryManagerProtocol,
    parameters: JSONDict,
) -> JSONDict:
    cursor_value = parameters.get("cursor")
    cursor = cursor_value if isinstance(cursor_value, str) else None
    page, next_cursor = manager.pagination.paginate_list(list(build_resource_templates()), cursor)
    return {
        "resourceTemplates": page,
        **({"nextCursor": next_cursor} if next_cursor else {}),
    }
