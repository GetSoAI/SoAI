"""SoAI - Per-conversation MCP tool catalog API routes [backend/features/api/routes/webui/conversation_mcp_tools_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends, Request

from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.mcp.tool_catalog_scope import (
    INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE,
    PUBLIC_MCP_TOOL_CATALOG_SCOPE,
)
from core.state.access import AccessAction
from core.types.json import JSONDict
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_mcp_catalog_state import (
    load_conversation_mcp_catalog_state,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.mcp_tool_catalog_payloads import (
    build_conversation_mcp_tool_catalog_response,
)
from features.api.schemas.mcp_config import ConversationMCPToolCatalogResponse

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.webui.get(
        "/conversations/{conv_id}/mcp/tools",
        response_model=ConversationMCPToolCatalogResponse,
        dependencies=require_action_dependencies(AccessAction.MCP_USE),
    )
    async def list_mcp_tools(
        request: Request,
        conv_id: str,
        current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONDict:
        state, tools_by_name = await load_conversation_mcp_catalog_state(
            request=request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=current_user["id"],
            local_tool_catalog_scope=(
                INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE
                if current_user["is_admin"]
                else PUBLIC_MCP_TOOL_CATALOG_SCOPE
            ),
        )
        disallowed_unqualified_tools = (
            load_automation_disallowed_unqualified_tools(api_context.dependencies.config)
            if state.is_automation
            else ()
        )
        return build_conversation_mcp_tool_catalog_response(
            conv_id=state.conv_id,
            tools_by_name=tools_by_name,
            normalized_mcp=state.effective_normalized_mcp,
            is_automation=state.is_automation,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        )
