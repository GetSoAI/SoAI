"""SoAI - MCP server request and task-tracking methods [backend/mcp/server/request_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from mcp.registry.internal_protocols import MCPRegistryManagerProtocol
from mcp.registry.tools_list import handle_tools_list
from mcp.server.dispatch import handle_mcp_request
from mcp.server.internal_protocols import (
    MCPBackgroundTaskSurface,
    MCPServerDispatchSurface,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "handle_mcp_request_method",
    "list_mcp_tools_method",
    "track_background_task_method",
)


async def list_mcp_tools_method(self: MCPRegistryManagerProtocol, parameters: JSONDict) -> JSONDict:
    normalized_parameters: JSONDict
    if isinstance(parameters, dict):
        normalized_parameters = dict(parameters)
    else:
        normalized_parameters = {}
    return await handle_tools_list(self, normalized_parameters)


def track_background_task_method(self: MCPBackgroundTaskSurface, task: asyncio.Task[None]) -> None:
    if task.done():
        return
    _ = self.background_tasks.track(task)


async def handle_mcp_request_method(
    self: MCPServerDispatchSurface,
    request_data: JSONDict,
    client_id: str,
    session_id: str | None = None,
    protocol_version: str | None = None,
) -> JSONDict:
    normalized_client_id = client_id.strip()
    resolved_client_id = normalized_client_id or client_id
    payload = request_data if isinstance(request_data, dict) else {}
    return await handle_mcp_request(
        self,
        payload,
        resolved_client_id,
        session_id,
        protocol_version,
    )
