"""SoAI - MCP task-service host-interaction methods [backend/mcp/server/handlers/task_service_host_interactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.mcp.protocols_runtime import MCPRemoteHostProtocol
from core.tasks.enums import TaskStatus
from core.timing.epoch import epoch_ms
from mcp.protocol.types import MCPJSONRPCError
from mcp.server.handlers.task_interactions import (
    expire_host_interaction,
    list_pending_host_interactions,
    resolve_host_interaction,
)
from mcp.server.handlers.task_payloads import build_task_response
from mcp.server.internal_protocols import MCPTaskStatusUpdateSurface

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "list_pending_host_interactions_method",
    "resolve_host_interaction_method",
)


async def list_pending_host_interactions_method(self: MCPTaskStatusUpdateSurface) -> list[JSONDict]:
    return await list_pending_host_interactions(self.require_task_registry_queries())


async def resolve_host_interaction_method(
    self: MCPTaskStatusUpdateSurface,
    remote: MCPRemoteHostProtocol,
    task_id: str,
    action: str,
    content: JSONDict | None = None,
) -> JSONDict:
    task = await self.get_task(task_id)
    if not task:
        raise MCPJSONRPCError(-32602, f"Task not found: {task_id}")
    if task.status != TaskStatus.INPUT_REQUIRED:
        raise MCPJSONRPCError(-32602, f"Task is not awaiting input: {task_id}")
    if task.ttl_expires_at_ms is not None and task.ttl_expires_at_ms <= epoch_ms():
        expired_task = await expire_host_interaction(self.server_ref, remote, task)
        if expired_task is None or expired_task.status == TaskStatus.FAILED:
            raise MCPJSONRPCError(-32603, "Timed out waiting for user input.")
        return build_task_response(expired_task)
    return await resolve_host_interaction(self.server_ref, remote, task, action, content)
