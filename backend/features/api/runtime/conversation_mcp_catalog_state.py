"""SoAI - Conversation MCP catalog and state loading [backend/features/api/runtime/conversation_mcp_catalog_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.tool_catalog import collect_mcp_tool_map
from core.mcp.tool_catalog_scope import (
    PUBLIC_MCP_TOOL_CATALOG_SCOPE,
    MCPToolCatalogScope,
)
from features.api.runtime.conversation_mcp_state import (
    ConversationMCPState,
    resolve_conversation_mcp_state,
)

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("load_conversation_mcp_catalog_state",)


async def load_conversation_mcp_catalog_state(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    conv_id: str,
    user_id: int,
    local_tool_catalog_scope: MCPToolCatalogScope,
    model_id_override: str | None = None,
) -> tuple[ConversationMCPState, dict[str, JSONDict]]:
    tool_map = await collect_mcp_tool_map(
        api_context.dependencies.mcp_server,
        api_context.dependencies.mcp_remote,
        api_context.dependencies.mcp_tool_catalog_cache,
        local_scope=local_tool_catalog_scope,
    )
    state = await resolve_conversation_mcp_state(
        request=request,
        api_context=api_context,
        conv_id=conv_id,
        user_id=user_id,
        model_id_override=model_id_override,
        available_tool_names=set(tool_map),
    )
    if state.is_automation and local_tool_catalog_scope != PUBLIC_MCP_TOOL_CATALOG_SCOPE:
        tool_map = await collect_mcp_tool_map(
            api_context.dependencies.mcp_server,
            api_context.dependencies.mcp_remote,
            api_context.dependencies.mcp_tool_catalog_cache,
            local_scope=PUBLIC_MCP_TOOL_CATALOG_SCOPE,
        )
        state = await resolve_conversation_mcp_state(
            request=request,
            api_context=api_context,
            conv_id=conv_id,
            user_id=user_id,
            model_id_override=model_id_override,
            available_tool_names=set(tool_map),
        )
    return (state, tool_map)
