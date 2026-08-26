"""SoAI - OpenAI-to-MCP tool call bridge execution [backend/mcp/bridge/openai.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.files.workspace_path_value import (
    coerce_workspace_path_value,
    require_workspace_path_value,
)
from core.licensing.enforcement import require_ordinary_licensing
from core.mcp.owner_keys import build_openai_conversation_owner_key
from core.mcp.protocols_main import (
    MCPRemoteProtocol,
    MCPSearchProtocol,
    MCPServerProtocol,
)
from core.runtime.request_context import RequestContext
from core.tool_calls.current_tool_call import CurrentToolCallIdentity
from core.tool_calls.tool_call_location import ToolCallLocation
from mcp.bridge.executor import (
    await_proxied_task_completion,
    execute_mcp_tool,
)
from mcp.bridge.handlers import build_builtin_tool_handlers
from mcp.registry.tool_execution_context import activate_openai_tool_context
from mcp.registry.tool_result_envelopes import extract_queued_task_id
from mcp.workspace_resolution import (
    ensure_runtime_workspace_path_from_user,
    propagate_runtime_workspace_path_for_tool_execution,
    set_runtime_workspace_path_for_owner_keys,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from mcp.rag.internal_protocols import MCPRAGInternalProtocol
    from mcp.tools.service import MCPUtilityTools

__all__ = ("OpenAIToolCallBridgeRequest", "execute_openai_tool_call_bridge")


@dataclass(frozen=True, slots=True)
class OpenAIToolCallBridgeRequest(ToolCallLocation):
    request_context: RequestContext
    user_id: int
    call_id: str
    storage_call_id: str


async def execute_openai_tool_call_bridge(
    mcp_server: MCPServerProtocol,
    mcp_remote: MCPRemoteProtocol,
    tool_name: str,
    arguments: JSONDict,
    *,
    bridge_request: OpenAIToolCallBridgeRequest,
    rag: MCPRAGInternalProtocol | None,
    mcp_search: MCPSearchProtocol | None,
    utility_tools: MCPUtilityTools,
    core_tool_handlers: Mapping[str, Callable[[JSONDict], Awaitable[JSONValue] | JSONValue]],
) -> JSONValue:
    await require_ordinary_licensing(mcp_server.licensing_status)
    request_context = bridge_request.request_context
    user_id = bridge_request.user_id
    owner_key = build_openai_conversation_owner_key(user_id=user_id, conv_id=bridge_request.conv_id)
    tool_call_identity = CurrentToolCallIdentity(
        user_id=bridge_request.user_id,
        conv_id=bridge_request.conv_id,
        message_index=bridge_request.message_index,
        assistant_at_ms=bridge_request.assistant_at_ms,
        assistant_turn_at_ms=bridge_request.assistant_turn_at_ms,
        model_variant_index=bridge_request.model_variant_index,
        sequence_index=bridge_request.sequence_index,
        content_index_before=bridge_request.content_index_before,
        thinking_index_before=bridge_request.thinking_index_before,
        turn_id=request_context.agent_turn_id,
        iteration_index=request_context.agent_iteration_index,
        storage_call_id=bridge_request.storage_call_id,
        call_id=bridge_request.call_id,
        tool_name=tool_name,
    )
    async with activate_openai_tool_context(
        mcp_server,
        utility_tools=utility_tools,
        owner_key=owner_key,
        user_id=int(user_id),
        request_context=request_context,
        tool_call_identity=tool_call_identity,
    ):
        workspace_value = request_context.agent_workspace_path
        resolved_workspace_path = coerce_workspace_path_value(workspace_value)
        if resolved_workspace_path is not None:
            set_runtime_workspace_path_for_owner_keys(
                runtime_sessions=utility_tools.runtime_sessions,
                workspace_path=resolved_workspace_path,
                owner_keys=(owner_key,),
            )
        else:
            resolved_workspace_path = await ensure_runtime_workspace_path_from_user(
                runtime_sessions=utility_tools.runtime_sessions,
                database_users=utility_tools.database_users,
                config=utility_tools.config,
                user_id=int(user_id),
                owner_key=owner_key,
            )
            require_workspace_path_value(
                resolved_workspace_path,
                error_message="workspace_path is not configured for MCP tool execution.",
            )
        propagate_runtime_workspace_path_for_tool_execution(
            utility_tools=utility_tools,
            tool_name=tool_name,
            arguments=arguments,
            owner_key=owner_key,
            workspace_path=str(resolved_workspace_path),
        )
        handlers = build_builtin_tool_handlers(
            request_context,
            user_id=user_id,
            conv_id=bridge_request.conv_id,
            rag=rag,
            mcp_search=mcp_search,
            utility_tools=utility_tools,
            core_tool_handlers=core_tool_handlers,
        )
        result = await execute_mcp_tool(mcp_remote, handlers, tool_name, arguments)
        proxied_task_id = extract_queued_task_id(result)
        if proxied_task_id:
            completion_payload = await await_proxied_task_completion(
                mcp_server,
                proxied_task_id,
                tool_name=tool_name,
            )
            if isinstance(result, dict):
                result.update(completion_payload)
        return result
