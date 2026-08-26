"""SoAI - MCP lifecycle task progress proxy handler [backend/mcp/server/handlers/lifecycle_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_tasks import TaskProgressEvent
from core.logging.trace import get_logger
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.status_transitions import update_progress
from mcp.server.state import MCPServerState

__all__ = ("handle_task_progress_event",)

LOGGER_NAME = "SoAI.mcp.server.lifecycle_progress"
OPERATION = "mcp.server.lifecycle.on_task_progress_event"


async def handle_task_progress_event(
    state: MCPServerState,
    task_registry: TaskRegistryProtocol,
    tasks_enabled: bool,
    event: TaskProgressEvent,
) -> None:
    logger = get_logger(LOGGER_NAME)
    if not tasks_enabled:
        return
    child_task_id = str(event.task_id or "").strip()
    if not child_task_id:
        return
    async with state.task.proxied_task_map_lock:
        parent_task_id = state.task.proxied_task_map.get(child_task_id)
    if not parent_task_id:
        return
    try:
        parent = await task_registry.get(parent_task_id)
        current = int(parent.progress_current or 0) if parent else 0
        incoming = int(event.percent)
        percent = max(0, min(100, max(current, incoming)))
        await update_progress(
            task_registry,
            parent_task_id,
            progress_current=percent,
            status_message=str(event.message or ""),
            details=str(event.details or ""),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to proxy task progress update (non-critical).",
            operation=OPERATION,
            details={"child_task_id": child_task_id, "parent_task_id": parent_task_id},
            level="debug",
        )
