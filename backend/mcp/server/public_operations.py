"""SoAI - MCP server public operations [backend/mcp/server/public_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine

from core.runtime.request_context import RequestContext
from core.types.json import JSONDict, JSONValue
from mcp.server.internal_protocols import (
    MCPBackgroundTaskSurface,
    MCPServerDispatchSurface,
    MCPServerRuntimeLifecycleSurface,
    MCPServerRuntimePropertiesSurface,
    OpenAIExecutionServerProtocol,
)
from mcp.server.openai_execution import (
    cancel_openai_shell_sessions_method,
    cancel_user_shell_sessions_method,
    execute_openai_tool_call_method,
)
from mcp.server.request_methods import (
    handle_mcp_request_method,
    track_background_task_method,
)
from mcp.server.runtime_properties import (
    list_registered_prompt_names,
    plugin_tool_definitions,
)
from mcp.server.service_runtime_attachment import (
    notify_resource_updated_method,
    schedule_background_task_method,
    shutdown_method,
    start_method,
)

__all__ = ("MCPServerOperations",)


class MCPServerOperations:
    async def handle_mcp_request(
        self: MCPServerDispatchSurface,
        request_data: JSONDict,
        client_id: str,
        session_id: str | None = None,
        protocol_version: str | None = None,
    ) -> JSONDict:
        return await handle_mcp_request_method(
            self,
            request_data,
            client_id,
            session_id,
            protocol_version,
        )

    def list_registered_prompt_names(
        self: MCPServerRuntimePropertiesSurface,
    ) -> list[str]:
        return list_registered_prompt_names(self)

    def plugin_tool_definitions(
        self: MCPServerRuntimePropertiesSurface,
    ) -> dict[str, JSONDict]:
        return plugin_tool_definitions(self)

    def track_background_task(self: MCPBackgroundTaskSurface, task: asyncio.Task[None]) -> None:
        track_background_task_method(self, task)

    async def execute_openai_tool_call(
        self: OpenAIExecutionServerProtocol,
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
        return await execute_openai_tool_call_method(
            self,
            tool_name,
            arguments,
            user_id=user_id,
            conv_id=conv_id,
            call_id=call_id,
            storage_call_id=storage_call_id,
            request_context=request_context,
            message_index=message_index,
            assistant_at_ms=assistant_at_ms,
            model_variant_index=model_variant_index,
            assistant_turn_at_ms=assistant_turn_at_ms,
            sequence_index=sequence_index,
            content_index_before=content_index_before,
            thinking_index_before=thinking_index_before,
        )

    async def cancel_openai_shell_sessions(
        self: OpenAIExecutionServerProtocol,
        *,
        user_id: int,
        conv_id: str,
    ) -> int:
        return await cancel_openai_shell_sessions_method(
            self,
            user_id=user_id,
            conv_id=conv_id,
        )

    async def cancel_user_shell_sessions(
        self: OpenAIExecutionServerProtocol,
        *,
        user_id: int,
    ) -> int:
        return await cancel_user_shell_sessions_method(self, user_id=user_id)

    def schedule_background_task(
        self: MCPServerRuntimeLifecycleSurface,
        coro: Coroutine[None, None, None],
        *,
        name: str,
    ) -> asyncio.Task[None]:
        return schedule_background_task_method(self, coro, name=name)

    async def start(self: MCPServerRuntimeLifecycleSurface) -> None:
        await start_method(self)

    async def shutdown(self: MCPServerRuntimeLifecycleSurface) -> None:
        await shutdown_method(self)

    async def notify_resource_updated(self: MCPServerRuntimeLifecycleSurface, uri: str) -> None:
        await notify_resource_updated_method(self, uri)
