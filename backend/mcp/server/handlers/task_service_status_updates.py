"""SoAI - MCP task status updates and notifications [backend/mcp/server/handlers/task_service_status_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.mcp.protocol_versions import DEFAULT_NEGOTIATED_PROTOCOL_VERSION
from core.metrics.keyspace_paths_mcp_server import (
    MCP_SERVER_COUNTER_TASKS_CANCELLED,
    MCP_SERVER_COUNTER_TASKS_COMPLETED,
    MCP_SERVER_COUNTER_TASKS_FAILED,
)
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from core.tasks.status_transitions import update_status
from core.tasks.task import Task
from core.tasks.task_cancellation import cancel
from mcp.protocol.jsonrpc import build_jsonrpc_notification
from mcp.server.handlers.task_payloads import build_task_response
from mcp.server.internal_protocols import MCPTaskStatusUpdateSurface

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "cancel_task_method",
    "complete_task_method",
    "create_input_required_task_method",
    "fail_task_method",
    "send_task_status_notification_method",
    "update_task_non_terminal_status_method",
    "update_task_to_terminal_status_method",
)

LOGGER_NAME = "SoAI.mcp.server.task_service_status_updates"


async def send_task_status_notification_method(
    self: MCPTaskStatusUpdateSurface,
    task: Task,
) -> None:
    response_payload = build_task_response(task)
    response_payload["_meta"] = {"io.modelcontextprotocol/related-task": task.task_id}
    notification = build_jsonrpc_notification("notifications/tasks/status", response_payload)
    notification_payload: JSONDict = dict(notification) if isinstance(notification, dict) else {}
    session_id = self.resolve_session_id(task.owner_id)
    session_exists = await self.has_client_session(session_id)
    if not session_exists:
        await self.ensure_client_session(session_id, DEFAULT_NEGOTIATED_PROTOCOL_VERSION, 0)
    await self.emit_client_stream_message(session_id, notification_payload)


async def update_task_to_terminal_status_method(
    self: MCPTaskStatusUpdateSurface,
    task_id: str,
    new_status: TaskStatus,
    result: JSONDict | None = None,
    error_code: int | None = None,
    error_message: str | None = None,
    status_message: str | None = None,
) -> None:
    logger = get_logger(LOGGER_NAME)
    task = await self.get_task(task_id)
    if not task or task.status.is_terminal():
        return
    task_registry = self.require_task_registry()
    if new_status == TaskStatus.COMPLETED:
        await finalize(
            task_registry,
            task_id,
            TaskStatus.COMPLETED,
            result=result,
            status_message=status_message,
        )
    elif new_status == TaskStatus.FAILED:
        await finalize(
            task_registry,
            task_id,
            TaskStatus.FAILED,
            error_code=error_code if error_code is not None else -32603,
            error_message=error_message or "Task failed",
            status_message=status_message,
        )
    elif new_status == TaskStatus.CANCELLED:
        await cancel(
            task_registry,
            task_id,
            reason=status_message or error_message or "Cancelled",
        )
    updated_task = await self.get_task(task_id)
    if updated_task:
        await self.send_task_status_notification(updated_task)
    status_counter = {
        TaskStatus.COMPLETED: MCP_SERVER_COUNTER_TASKS_COMPLETED,
        TaskStatus.FAILED: MCP_SERVER_COUNTER_TASKS_FAILED,
        TaskStatus.CANCELLED: MCP_SERVER_COUNTER_TASKS_CANCELLED,
    }.get(new_status)
    if status_counter:
        self.metrics_manager.increment_counter(*status_counter)
    logger.debug(
        "Task %s %s%s",
        task_id,
        new_status.value,
        f": {error_message}" if error_message else "",
    )


async def complete_task_method(
    self: MCPTaskStatusUpdateSurface,
    task_id: str,
    result: JSONDict,
    message: str | None = None,
) -> None:
    await self.update_task_to_terminal_status(
        task_id,
        TaskStatus.COMPLETED,
        result=result,
        status_message=(message if message is not None else None),
    )


async def fail_task_method(
    self: MCPTaskStatusUpdateSurface,
    task_id: str,
    code: int,
    message: str,
) -> None:
    await self.update_task_to_terminal_status(
        task_id,
        TaskStatus.FAILED,
        error_code=code,
        error_message=message,
    )


async def cancel_task_method(
    self: MCPTaskStatusUpdateSurface,
    task_id: str,
    reason: str = "Cancelled",
) -> None:
    await self.update_task_to_terminal_status(task_id, TaskStatus.CANCELLED, error_message=reason)


async def update_task_non_terminal_status_method(
    self: MCPTaskStatusUpdateSurface,
    task_id: str,
    status: TaskStatus,
    message: str,
) -> None:
    task = await self.get_task(task_id)
    if not task or task.status.is_terminal():
        return
    task_registry = self.require_task_registry()
    await update_status(task_registry, task_id, status, status_message=message)
    updated_task = await self.get_task(task_id)
    if updated_task:
        await self.send_task_status_notification(updated_task)


async def create_input_required_task_method(
    self: MCPTaskStatusUpdateSurface,
    server_id: str,
    method: str,
    parameters: JSONDict,
    message: str,
) -> JSONDict:
    task = await self.create_task(server_id, method, parameters)
    await self.update_task_non_terminal_status(task.task_id, TaskStatus.INPUT_REQUIRED, message)
    updated_task = await self.get_task(task.task_id)
    return {"task": build_task_response(updated_task or task)}
