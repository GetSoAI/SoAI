"""SoAI - MCP management status routes [backend/features/api/routes/mcp/routes/management_status_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends
from fastapi.responses import JSONResponse

from core.mcp.protocols_main import MCPRemoteProtocol
from core.mcp.protocols_storage import DatabaseMCPProtocol
from core.state.access import AccessAction
from core.types.json_value import require_json_dict_list
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.mcp.get("/status", dependencies=require_action_dependencies(AccessAction.MCP_USE))
    async def get_mcp_status(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONResponse:
        mcp_server_instance = api_context.dependencies.mcp_server
        mcp_remote_instance = api_context.dependencies.mcp_remote
        mcp_database: DatabaseMCPProtocol = api_context.dependencies.database_mcp
        mcp_remote: MCPRemoteProtocol = mcp_remote_instance
        connections = require_json_dict_list(
            await mcp_remote.list_connected_servers(),
            label="MCP connections",
        )
        connected_servers = len(
            [connection for connection in connections if connection.get("status") == "connected"],
        )
        total_servers = len(
            require_json_dict_list(await mcp_database.get_all_mcp_servers(), label="MCP servers"),
        )
        return JSONResponse(
            content={
                "enabled": mcp_server_instance.enabled,
                "host_mode": {
                    "enabled": mcp_server_instance.host_mode_enabled,
                    "connected_servers": connected_servers,
                    "total_servers": total_servers,
                    "connection_entries": len(connections),
                },
                "server_mode": {
                    "enabled": mcp_server_instance.server_mode_enabled,
                    "active": mcp_server_instance.server_mode_active,
                    "tools_count": mcp_server_instance.registered_tools_count,
                    "resources_count": mcp_server_instance.registered_resources_count,
                },
            },
        )
