"""SoAI - MCP management client routes (host interactions and roots) [backend/features/api/routes/mcp/routes/management_client_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.errors.external_service_exception import MCPError
from core.state.access import AccessAction
from core.types.json_value import require_json_dict, require_json_dict_list
from features.api.routes.mcp.route_errors import raise_mcp_route_error
from features.api.runtime.access_dependencies import (
    require_action_dependencies,
    restart_protected_dependencies,
)
from features.api.runtime.audit import log_audit_event
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.schemas.mcp import MCPHostInteractionResolve, MCPHostRootsUpdate

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.mcp.get(
        "/client/interactions",
        dependencies=require_action_dependencies(AccessAction.MCP_USE),
    )
    async def list_mcp_client_interactions(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        interactions = (
            await api_context.dependencies.mcp_server.task.list_pending_host_interactions()
        )
        return JSONResponse(
            content=require_json_dict_list(interactions, label="MCP host interactions"),
        )

    @routers.mcp.post(
        "/client/interactions/{task_id}/resolve",
        status_code=200,
        dependencies=restart_protected_dependencies(AccessAction.MCP_USE),
    )
    async def resolve_mcp_client_interaction(
        request: Request,
        task_id: str,
        payload: MCPHostInteractionResolve,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            resolved = await api_context.dependencies.mcp_server.task.resolve_host_interaction(
                api_context.dependencies.mcp_remote,
                task_id,
                payload.action,
                payload.content,
            )
            return JSONResponse(
                content=require_json_dict(resolved, label="MCP host interaction resolve response"),
            )
        except MCPError as exception:
            raise_mcp_route_error(request, exception, error_type="mcp_interaction_error")

    @routers.mcp.get(
        "/client/roots",
        dependencies=require_action_dependencies(AccessAction.MCP_USE),
    )
    async def get_mcp_client_roots(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        roots = api_context.dependencies.mcp_remote.get_host_roots()
        return JSONResponse(content={"roots": require_json_dict_list(roots, label="MCP roots")})

    @routers.mcp.put(
        "/client/roots",
        status_code=200,
        dependencies=restart_protected_dependencies(AccessAction.MCP_USE),
    )
    async def update_mcp_client_roots(
        request: Request,
        payload: MCPHostRootsUpdate,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        try:
            roots_payload: list[JSONValue] = []
            for root in payload.roots:
                if isinstance(root, dict):
                    roots_payload.append(require_json_dict(root, label="MCP roots"))
                else:
                    roots_payload.append(root)
            roots = await api_context.dependencies.mcp_remote.set_host_roots(roots_payload)
            log_audit_event(request, "MCP_CLIENT_ROOTS_UPDATED", "roots", {"count": len(roots)})
            return JSONResponse(content={"roots": require_json_dict_list(roots, label="MCP roots")})
        except MCPError as exception:
            raise_mcp_route_error(request, exception, error_type="mcp_roots_error")
