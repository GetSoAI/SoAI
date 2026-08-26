"""SoAI - Automation MCP tool catalog routes [backend/features/api/routes/automations/mcp_tools_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import Depends

from core.automation.automation_mcp_config import normalize_automation_mcp_settings
from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.mcp.tool_catalog import collect_mcp_tool_catalog
from core.mcp.tool_catalog_scope import PUBLIC_MCP_TOOL_CATALOG_SCOPE
from core.state.access import AccessAction
from core.types.json import JSONDict
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.mcp_tool_catalog_payloads import (
    build_automation_mcp_tool_catalog_response,
)
from features.api.schemas.mcp_config import AutomationMCPToolCatalogResponse

__all__ = ("register_routes",)


def register_routes(routers: ApiRouters) -> None:
    @routers.automations.get(
        "/mcp/tools",
        response_model=AutomationMCPToolCatalogResponse,
        dependencies=require_action_dependencies(AccessAction.MCP_USE),
    )
    async def list_automation_mcp_tools(
        _current_user: CurrentUser = Depends(get_current_user),
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> JSONDict:
        _, tools_by_name = await collect_mcp_tool_catalog(
            api_context.dependencies.mcp_server,
            api_context.dependencies.mcp_remote,
            api_context.dependencies.mcp_tool_catalog_cache,
            local_scope=PUBLIC_MCP_TOOL_CATALOG_SCOPE,
        )
        disallowed_unqualified_tools = load_automation_disallowed_unqualified_tools(
            api_context.dependencies.config,
        )
        normalized = normalize_automation_mcp_settings(
            None,
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        )
        return build_automation_mcp_tool_catalog_response(
            tools_by_name=tools_by_name,
            execute_tools=list(normalized.execute_tools),
            disallowed_unqualified_tools=disallowed_unqualified_tools,
        )
