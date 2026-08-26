"""SoAI - MCP management server routes (servers and connections) [backend/features/api/routes/mcp/routes/management_server_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.exceptions import StateError, ValidationError
from core.mcp.requests import AddMCPServerRequest
from core.state.access import AccessAction
from core.state.errors import DuplicateMCPServerError
from core.types.json_value import require_json_dict, require_json_dict_list
from features.api.routes.mcp.routes.management_server_rows import (
    coerce_mcp_server_config_or_raise,
    load_mcp_server_row_or_raise,
    require_server_id_or_raise,
)
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.errors import (
    raise_conflict,
    raise_forbidden,
    raise_invalid_request,
    raise_not_found,
    raise_server_error,
    raise_unauthorized,
)
from features.api.runtime.responses import create_no_content_response
from features.api.schemas.mcp import MCPServerCreate, MCPServerUpdate

__all__ = (
    "add_mcp_server",
    "connect_mcp_server",
    "disconnect_mcp_server",
    "list_mcp_connections",
    "list_mcp_servers",
    "register_endpoints",
    "register_routes",
    "remove_mcp_server",
    "update_mcp_server",
)


async def list_mcp_servers(api_context: ApiContext = Depends(resolve_api_context)) -> Response:
    servers = await api_context.dependencies.database_mcp.get_all_mcp_servers()
    return JSONResponse(content=require_json_dict_list(servers, label="MCP servers"))


async def add_mcp_server(
    request: Request,
    payload: MCPServerCreate,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    try:
        config = await api_context.dependencies.mcp_remote.add_server(
            AddMCPServerRequest(
                name=payload.name,
                transport_type=payload.transport_type,
                endpoint=payload.endpoint,
                arguments=payload.args,
                env=payload.env,
                headers=payload.headers,
                api_key=payload.api_key,
                timeout_ms=payload.timeout_ms,
                auto_reconnect=payload.auto_reconnect,
            ),
        )
        server_id = config.id
        server_name = config.name
        log_audit_event(request, "MCP_SERVER_ADDED", server_id, {"name": server_name})
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"id": server_id, "name": server_name, "status": "created"},
        )
    except DuplicateMCPServerError as exception:
        raise_conflict(request, str(exception), error_type="conflict")
    except (StateError, ValidationError, ValueError) as exception:
        raise_invalid_request(request, str(exception))


async def update_mcp_server(
    request: Request,
    server_id: str,
    payload: MCPServerUpdate,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    normalized_server_id = require_server_id_or_raise(request, server_id)
    mcp_remote_instance = api_context.dependencies.mcp_remote
    mcp_database = api_context.dependencies.database_mcp
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise_invalid_request(request, "No update data provided.")
    connections = await mcp_remote_instance.list_connected_servers()
    for connection in connections:
        if connection.get("id") != normalized_server_id:
            continue
        if connection.get("status") in ("connected", "connecting"):
            raise_conflict(
                request,
                f"MCP server '{normalized_server_id}' is currently {connection.get('status')}; disconnect before updating.",
            )
    try:
        updated = await mcp_database.update_mcp_server(normalized_server_id, updates)
    except (StateError, ValidationError, ValueError) as exception:
        raise_invalid_request(request, str(exception))
    if not updated:
        raise_not_found(request, f"MCP server '{normalized_server_id}' not found.")
    try:
        server_row = await mcp_database.get_mcp_server(normalized_server_id, decrypt_key=True)
    except (StateError, ValidationError) as exception:
        raise_server_error(request, str(exception), error_type="invalid_server_state")
    if server_row:
        config = coerce_mcp_server_config_or_raise(request, server_row)
        await mcp_remote_instance.update_cached_server_config(config)
    log_audit_event(
        request,
        "MCP_SERVER_UPDATED",
        normalized_server_id,
        {"updated_fields": sorted(updates.keys())},
    )
    return JSONResponse(content=require_json_dict(updated, label="MCP server"))


async def remove_mcp_server(
    request: Request,
    server_id: str,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    normalized_server_id = require_server_id_or_raise(request, server_id)
    try:
        deleted = await api_context.dependencies.mcp_remote.remove_server(normalized_server_id)
    except (StateError, ValidationError) as exception:
        raise_invalid_request(request, str(exception))
    if not deleted:
        raise_not_found(request, f"MCP server '{normalized_server_id}' not found.")
    log_audit_event(request, "MCP_SERVER_REMOVED", normalized_server_id)
    return create_no_content_response()


async def connect_mcp_server(
    request: Request,
    server_id: str,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    normalized_server_id, server_row = await load_mcp_server_row_or_raise(
        request,
        api_context,
        server_id=server_id,
        decrypt_key=True,
    )
    config = coerce_mcp_server_config_or_raise(request, server_row)
    success = await api_context.dependencies.mcp_remote.connect_to_server(config)
    if not success:
        try:
            status_row = await api_context.dependencies.database_mcp.get_mcp_server(
                normalized_server_id,
                decrypt_key=False,
            )
        except (StateError, ValidationError) as exception:
            raise_server_error(request, str(exception), error_type="invalid_server_state")
        if status_row and status_row.get("status") == "auth_required":
            oauth_status = status_row.get("oauth_status")
            last_error = status_row.get("last_error")
            error_message = (
                str(last_error)
                if isinstance(last_error, str) and last_error.strip()
                else "Authorization required."
            )
            if oauth_status == "insufficient_scope":
                raise_forbidden(
                    request,
                    error_message,
                    error_type="insufficient_scope",
                )
            raise_unauthorized(
                request,
                error_message,
                error_type="auth_required",
            )
        raise_server_error(
            request,
            f"Failed to connect to MCP server '{normalized_server_id}'.",
            error_type="connection_failed",
        )
    log_audit_event(
        request,
        "MCP_SERVER_CONNECTED",
        normalized_server_id,
        {"name": normalized_server_id},
    )
    return JSONResponse(content={"status": "connected", "server_id": normalized_server_id})


async def disconnect_mcp_server(
    request: Request,
    server_id: str,
    api_context: ApiContext = Depends(resolve_api_context),
) -> Response:
    normalized_server_id = require_server_id_or_raise(request, server_id)
    try:
        disconnected = await api_context.dependencies.mcp_remote.disconnect_from_server(
            normalized_server_id,
        )
    except (StateError, ValidationError) as exception:
        raise_invalid_request(request, str(exception))
    if not disconnected:
        raise_not_found(
            request,
            f"MCP server '{normalized_server_id}' not found or not connected.",
        )
    log_audit_event(request, "MCP_SERVER_DISCONNECTED", normalized_server_id)
    return JSONResponse(content={"status": "disconnected", "server_id": normalized_server_id})


async def list_mcp_connections(api_context: ApiContext = Depends(resolve_api_context)) -> Response:
    connections = await api_context.dependencies.mcp_remote.list_connected_servers()
    return JSONResponse(content=require_json_dict_list(connections, label="MCP connections"))


def register_endpoints(router: APIRouter) -> None:
    router.get(
        "/servers",
        dependencies=require_action_dependencies(AccessAction.MCP_ADMIN),
    )(list_mcp_servers)
    router.post(
        "/servers",
        status_code=201,
        dependencies=restart_protected_dependencies(AccessAction.MCP_ADMIN),
    )(add_mcp_server)
    router.patch(
        "/servers/{server_id}",
        status_code=200,
        dependencies=restart_protected_dependencies(AccessAction.MCP_ADMIN),
    )(update_mcp_server)
    router.delete(
        "/servers/{server_id}",
        status_code=204,
        dependencies=restart_protected_dependencies(AccessAction.MCP_ADMIN),
    )(remove_mcp_server)
    router.post(
        "/servers/{server_id}/connect",
        status_code=200,
        dependencies=restart_protected_dependencies(AccessAction.MCP_ADMIN),
    )(connect_mcp_server)
    router.post(
        "/servers/{server_id}/disconnect",
        status_code=200,
        dependencies=restart_protected_dependencies(AccessAction.MCP_ADMIN),
    )(disconnect_mcp_server)
    router.get(
        "/connections",
        dependencies=require_action_dependencies(AccessAction.MCP_ADMIN),
    )(list_mcp_connections)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.mcp)
