"""SoAI - MCP remote background task scheduling [backend/mcp/remote/service_background_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Coroutine

from core.concurrency.background_task_scheduling import schedule_named_background_task
from core.logging.trace import get_logger
from mcp.remote.internal_protocols import MCPRemoteBackgroundTaskSurface

__all__ = ("schedule_background_task_method",)

LOGGER_NAME = "SoAI.mcp.remote.service_background_tasks"
OPERATION_MCP_REMOTE_SCHEDULE_BACKGROUND_TASK = "mcp.remote.schedule_background_task"


def schedule_background_task_method(
    self: MCPRemoteBackgroundTaskSurface,
    coro: Coroutine[None, None, None],
    *,
    name: str,
) -> asyncio.Task[None]:
    return schedule_named_background_task(
        coro,
        name=name,
        track_task=self.track_background_task,
        logger=get_logger(LOGGER_NAME),
        operation=OPERATION_MCP_REMOTE_SCHEDULE_BACKGROUND_TASK,
        empty_name_error_message="MCP remote background task name must be a non-empty string.",
        close_failure_message="Failed to close MCP remote background coroutine (non-critical).",
    )
