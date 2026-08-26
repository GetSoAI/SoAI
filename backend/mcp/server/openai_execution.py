"""SoAI - MCP OpenAI execution helpers [backend/mcp/server/openai_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from core.mcp.owner_keys import build_openai_conversation_owner_key
from core.runtime.request_context import RequestContext
from core.types.json import JSONDict, JSONValue
from mcp.bridge.openai import OpenAIToolCallBridgeRequest, execute_openai_tool_call_bridge
from mcp.server.internal_protocols import OpenAIExecutionServerProtocol
from mcp.tools.shell_session_cleanup import (
    ShellSessionCleanupDeps,
    close_shell_session_resources,
)

__all__ = (
    "cancel_openai_shell_sessions_method",
    "cancel_user_shell_sessions_method",
    "execute_openai_tool_call_method",
)

LOGGER_NAME = "SoAI.mcp.server.openai_execution"
OPERATION = "mcp.server.cancel_openai_shell_sessions"
OPERATION_CANCEL_USER = "mcp.server.cancel_user_shell_sessions"


async def execute_openai_tool_call_method(
    server: OpenAIExecutionServerProtocol,
    tool_name: str,
    arguments: JSONDict,
    *,
    request_context: RequestContext,
    user_id: int,
    conv_id: str,
    call_id: str,
    storage_call_id: str,
    message_index: int,
    assistant_at_ms: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    sequence_index: int,
    content_index_before: int,
    thinking_index_before: int,
) -> JSONValue:
    return await execute_openai_tool_call_bridge(
        server,
        server.mcp_remote,
        tool_name,
        arguments,
        bridge_request=OpenAIToolCallBridgeRequest(
            request_context=request_context,
            user_id=user_id,
            conv_id=conv_id,
            call_id=call_id,
            storage_call_id=storage_call_id,
            message_index=message_index,
            assistant_at_ms=assistant_at_ms,
            assistant_turn_at_ms=assistant_turn_at_ms,
            model_variant_index=model_variant_index,
            sequence_index=sequence_index,
            content_index_before=content_index_before,
            thinking_index_before=thinking_index_before,
        ),
        rag=server.state.mcp_rag,
        mcp_search=server.state.mcp_search,
        utility_tools=server.utility_tools,
        core_tool_handlers=server.core_tool_handlers,
    )


async def cancel_openai_shell_sessions_method(
    server: OpenAIExecutionServerProtocol,
    *,
    user_id: int,
    conv_id: str,
) -> int:
    owner_key = build_openai_conversation_owner_key(user_id=user_id, conv_id=conv_id)
    sessions = server.utility_tools.runtime_sessions.list_shell_sessions_for_owner(
        owner_key=owner_key,
    )
    logger = get_logger(LOGGER_NAME)
    cleanup_deps = ShellSessionCleanupDeps(
        runtime_sessions=server.utility_tools.runtime_sessions,
        terminal=server.utility_tools.terminal,
        logger=logger,
    )
    closed_count = 0
    for session in sessions:
        await close_shell_session_resources(
            cleanup_deps,
            operation=OPERATION,
            shell_session_id=session.session_id,
            terminal_session_id=session.terminal_session_id,
        )
        closed_count += 1
    return closed_count


async def cancel_user_shell_sessions_method(
    server: OpenAIExecutionServerProtocol,
    *,
    user_id: int,
) -> int:
    sessions = server.utility_tools.runtime_sessions.list_shell_sessions_for_user(user_id)
    logger = get_logger(LOGGER_NAME)
    cleanup_deps = ShellSessionCleanupDeps(
        runtime_sessions=server.utility_tools.runtime_sessions,
        terminal=server.utility_tools.terminal,
        logger=logger,
    )
    closed_count = 0
    for session in sessions:
        await close_shell_session_resources(
            cleanup_deps,
            operation=OPERATION_CANCEL_USER,
            shell_session_id=session.session_id,
            terminal_session_id=session.terminal_session_id,
        )
        closed_count += 1
    return closed_count
