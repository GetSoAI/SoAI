"""SoAI - MCP server runtime attachment and lifecycle [backend/mcp/server/service_runtime_attachment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine

from core.concurrency.background_task_scheduling import schedule_named_background_task
from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from mcp.server.internal_protocols import MCPServerRuntimeLifecycleSurface

__all__ = (
    "notify_resource_updated_method",
    "schedule_background_task_method",
    "shutdown_method",
    "start_method",
)

LOGGER_NAME = "SoAI.mcp.server.service_runtime_attachment"
OPERATION_MCP_SERVER_SCHEDULE_BACKGROUND_TASK = "mcp.server.schedule_background_task"


def schedule_background_task_method(
    self: MCPServerRuntimeLifecycleSurface,
    coro: Coroutine[None, None, None],
    *,
    name: str,
) -> asyncio.Task[None]:
    return schedule_named_background_task(
        coro,
        name=name,
        track_task=self.track_background_task,
        logger=get_logger(LOGGER_NAME),
        operation=OPERATION_MCP_SERVER_SCHEDULE_BACKGROUND_TASK,
        empty_name_error_message="MCP server background task name must be a non-empty string.",
        close_failure_message="Failed to close MCP server background coroutine (non-critical).",
    )


async def start_method(self: MCPServerRuntimeLifecycleSurface) -> None:
    manager = self.lifecycle_manager
    if manager is None:
        raise StateError("MCPServer runtime bundle is not attached.")
    await manager.start()


async def shutdown_method(self: MCPServerRuntimeLifecycleSurface) -> None:
    manager = self.lifecycle_manager
    if manager is None:
        raise StateError("MCPServer runtime bundle is not attached.")
    await manager.shutdown()


async def notify_resource_updated_method(self: MCPServerRuntimeLifecycleSurface, uri: str) -> None:
    notification = self.notification
    await notification.notify_resource_updated(uri)
