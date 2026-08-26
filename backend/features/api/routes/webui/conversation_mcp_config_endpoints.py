"""SoAI - Per-conversation MCP configuration API routes [backend/features/api/routes/webui/conversation_mcp_config_endpoints.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from core.automation.automation_tool_blocklist import (
    load_automation_disallowed_unqualified_tools,
)
from core.mcp.tool_catalog_scope import (
    INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE,
    PUBLIC_MCP_TOOL_CATALOG_SCOPE,
    MCPToolCatalogScope,
)
from core.state.access import AccessAction
from core.types.json import JSONDict
from features.api.runtime.access_dependencies import require_action_dependencies
from features.api.runtime.container.api_routers import ApiRouters
from features.api.runtime.context import ApiContext, resolve_api_context
from features.api.runtime.conversation_access import (
    require_conversation_access,
    resolve_conversation_access_id,
)
from features.api.runtime.conversation_mcp_catalog_state import (
    load_conversation_mcp_catalog_state,
)
from features.api.runtime.conversation_mcp_state import (
    build_conversation_mcp_config_payload,
    resolve_conversation_mcp_state,
)
from features.api.runtime.conversation_mcp_state_merge import (
    merge_conversation_mcp_config_update,
)
from features.api.runtime.conversation_model_settings import (
    update_conversation_model_settings,
)
from features.api.runtime.current_user import CurrentUser, get_current_user
from features.api.runtime.mcp_enabled_mode_validation import (
    validate_enabled_tools_for_agent_mode,
)
from features.api.runtime.mcp_server_configs_validation import load_mcp_server_ids
from features.api.schemas.mcp_config import (
    ConversationMCPConfigResponse,
    ConversationMCPConfigUpdate,
)

__all__ = (
    "get_mcp_config",
    "register_endpoints",
    "register_routes",
    "update_mcp_config",
)


async def get_mcp_config(
    request: Request,
    conv_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONDict:
    state, _tool_map = await load_conversation_mcp_catalog_state(
        request=request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
        local_tool_catalog_scope=_local_tool_catalog_scope(current_user),
    )
    return build_conversation_mcp_config_payload(state)


async def update_mcp_config(
    request: Request,
    conv_id: str,
    payload: ConversationMCPConfigUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    api_context: ApiContext = Depends(resolve_api_context),
) -> JSONDict:
    conversation = await require_conversation_access(
        request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=current_user["id"],
    )
    resolved_conv_id = resolve_conversation_access_id(conversation, conv_id)
    async with api_context.dependencies.conversation_agent_settings_locks.lock(
        (current_user["id"], resolved_conv_id),
    ):
        state, tool_map = await load_conversation_mcp_catalog_state(
            request=request,
            api_context=api_context,
            conv_id=resolved_conv_id,
            user_id=current_user["id"],
            local_tool_catalog_scope=_local_tool_catalog_scope(current_user),
        )
        server_ids = (
            await load_mcp_server_ids(api_context.dependencies.database_mcp)
            if "server_configs" in payload.model_fields_set
            else set[str]()
        )
        settings = dict(state.settings)
        mcp_config = merge_conversation_mcp_config_update(
            request=request,
            state=state,
            payload=payload,
            tool_map=tool_map,
            server_ids=server_ids,
            disallowed_unqualified_tools=load_automation_disallowed_unqualified_tools(
                api_context.dependencies.config,
            ),
        )
        settings["mcp"] = mcp_config
        validate_enabled_tools_for_agent_mode(
            request=request,
            settings=settings,
            merged_config=mcp_config,
        )
        updated_record = await update_conversation_model_settings(
            request,
            api_context=api_context,
            conv_id=state.conv_id,
            user_id=current_user["id"],
            model_settings=settings,
        )
        updated_conv_id = resolve_conversation_access_id(updated_record, state.conv_id)
        updated_state = await resolve_conversation_mcp_state(
            request=request,
            api_context=api_context,
            conv_id=updated_conv_id,
            user_id=current_user["id"],
            available_tool_names=set(tool_map),
            conversation_record=updated_record,
        )
    return build_conversation_mcp_config_payload(updated_state)


def _local_tool_catalog_scope(current_user: CurrentUser) -> MCPToolCatalogScope:
    if current_user["is_admin"]:
        return INTERNAL_ADMIN_MCP_TOOL_CATALOG_SCOPE
    return PUBLIC_MCP_TOOL_CATALOG_SCOPE


def register_endpoints(router: APIRouter) -> None:
    mcp_use_deps = require_action_dependencies(AccessAction.MCP_USE)
    router.get(
        "/conversations/{conv_id}/mcp/config",
        response_model=ConversationMCPConfigResponse,
        dependencies=mcp_use_deps,
    )(get_mcp_config)
    router.patch(
        "/conversations/{conv_id}/mcp/config",
        response_model=ConversationMCPConfigResponse,
        dependencies=mcp_use_deps,
    )(update_mcp_config)


def register_routes(routers: ApiRouters) -> None:
    register_endpoints(routers.webui)
