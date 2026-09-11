"""SoAI - Owner Messaging account MCP catalog route [backend/features/api/routes/webui/messaging_account_mcp_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends

from core.mcp.tool_catalog import collect_mcp_tool_map
from core.mcp.tool_catalog_scope import (
    resolve_conversation_tool_catalog_scope,
)
from core.state.access import AccessAction
from core.types.json import JSONDict
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.mcp_tool_catalog_payloads import (
    build_messaging_mcp_tool_catalog_response,
)
from features.api.schemas.mcp_config import MessagingMCPToolCatalogResponse

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/messaging/mcp/tools",
        response_model=MessagingMCPToolCatalogResponse,
        dependencies=require_action_dependencies(AccessAction.MCP_USE),
    )
    async def list_messaging_mcp_tools(
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONDict:
        tools_by_name = await collect_mcp_tool_map(
            api_context.dependencies.mcp_server,
            api_context.dependencies.mcp_remote,
            api_context.dependencies.mcp_tool_catalog_cache,
            local_scope=resolve_conversation_tool_catalog_scope(
                user_is_admin=current_user["is_admin"],
            ),
        )
        return build_messaging_mcp_tool_catalog_response(
            tools_by_name=tools_by_name,
        )
