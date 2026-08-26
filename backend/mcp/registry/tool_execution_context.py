"""SoAI - MCP tool execution context scopes [backend/mcp/registry/tool_execution_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import contextvars
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.mcp.protocols_main import MCPServerProtocol
    from core.runtime.request_context import RequestContext
    from core.tool_calls.current_tool_call import CurrentToolCallIdentity
    from mcp.registry.internal_protocols import MCPRegistryManagerProtocol
    from mcp.tools.service import MCPUtilityTools

__all__ = (
    "RegistryToolExecutionContext",
    "activate_openai_tool_context",
    "activate_registry_tool_context",
)


@dataclass(frozen=True, slots=True)
class RegistryToolExecutionContext:
    user_id: int
    client_id: str
    task_id: str | None


@asynccontextmanager
async def activate_registry_tool_context(
    manager: MCPRegistryManagerProtocol,
    *,
    client_id: str,
    task_id: str | None = None,
) -> AsyncGenerator[RegistryToolExecutionContext]:
    client_token = manager.context.set_active_client_context(client_id)
    user_id, _ = manager.context.current_session_identity()
    user_token = manager.context.set_active_user_id_context(user_id)
    task_token: contextvars.Token[str | None] | None = None
    if task_id is not None:
        task_token = manager.context.set_active_task_context(task_id)
    try:
        yield RegistryToolExecutionContext(user_id=user_id, client_id=client_id, task_id=task_id)
    finally:
        if task_token is not None:
            manager.context.reset_active_task_context(task_token)
        manager.context.reset_active_user_id_context(user_token)
        manager.context.reset_active_client_context(client_token)


@asynccontextmanager
async def activate_openai_tool_context(
    mcp_server: MCPServerProtocol,
    *,
    utility_tools: MCPUtilityTools,
    owner_key: str,
    user_id: int,
    request_context: RequestContext,
    tool_call_identity: CurrentToolCallIdentity,
) -> AsyncGenerator[None]:
    client_token = mcp_server.context.set_active_client_context(owner_key)
    user_token = mcp_server.context.set_active_user_id_context(user_id)
    tool_call_token = utility_tools.active_tool_call_context.set(tool_call_identity)
    request_context_token = utility_tools.active_request_context.set(request_context)
    try:
        yield None
    finally:
        utility_tools.active_request_context.reset(request_context_token)
        utility_tools.active_tool_call_context.reset(tool_call_token)
        mcp_server.context.reset_active_user_id_context(user_token)
        mcp_server.context.reset_active_client_context(client_token)
