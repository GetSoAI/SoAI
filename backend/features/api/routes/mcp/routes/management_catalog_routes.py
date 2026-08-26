"""SoAI - MCP tool, resource, and prompt management routes [backend/features/api/routes/mcp/routes/management_catalog_routes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from core.mcp.tool_entries import SOAI_MCP_SERVER_NAME, build_tool_entry
from core.state.access import AccessAction
from core.types.json_value import require_json_dict_list
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("register_routes",)


def _build_local_tool_entries(
    tool_names: list[str],
    tool_definitions: Mapping[str, JSONDict],
) -> list[JSONDict]:
    tools: list[JSONDict] = []
    for name in sorted(tool_names):
        definition = tool_definitions.get(name)
        if not isinstance(definition, Mapping):
            continue
        entry = build_tool_entry(name=name, definition=definition)
        entry["server_id"] = None
        entry["server_name"] = SOAI_MCP_SERVER_NAME
        tools.append(entry)
    return tools


def register_routes(routers: ApiRouters) -> None:
    @routers.mcp.get("/tools", dependencies=require_action_dependencies(AccessAction.MCP_USE))
    async def list_mcp_tools(
        _request: Request,
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        mcp_server_instance = api_context.dependencies.mcp_server
        remote_tools = require_json_dict_list(
            await api_context.dependencies.mcp_remote.list_all_tools(),
            label="MCP tools",
        )
        local_tools = _build_local_tool_entries(
            mcp_server_instance.registration.registered_tool_names(),
            mcp_server_instance.registration.tool_definitions(),
        )
        combined = remote_tools + local_tools
        return JSONResponse(content=combined)

    @routers.mcp.get("/resources", dependencies=require_action_dependencies(AccessAction.MCP_USE))
    async def mcp_resources_list(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        resources = await api_context.dependencies.mcp_remote.list_all_resources()
        return JSONResponse(content=require_json_dict_list(resources, label="MCP resources"))

    @routers.mcp.get("/prompts", dependencies=require_action_dependencies(AccessAction.MCP_USE))
    async def list_mcp_prompts(
        api_context: ApiContext = Depends(resolve_api_context),
    ) -> Response:
        prompts = await api_context.dependencies.mcp_remote.list_all_prompts()
        return JSONResponse(content=require_json_dict_list(prompts, label="MCP prompts"))
