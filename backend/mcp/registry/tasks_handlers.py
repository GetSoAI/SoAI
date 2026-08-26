"""SoAI - MCP task method handlers [backend/mcp/registry/tasks_handlers.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.tasks.protocols import TaskRegistryProtocol
from core.tasks.task import Task
from core.tasks.task_cancellation import cancel
from core.timing.formatting import timestamp_ms_to_utc_iso
from mcp.protocol.types import MCPJSONRPCError
from mcp.registry.internal_protocols import MCPTaskHandlerManagerProtocol
from mcp.server.handlers.task_payloads import (
    build_task_response,
    extract_task_id_parameter,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "handle_tasks_cancel",
    "handle_tasks_get",
    "handle_tasks_list",
    "handle_tasks_result",
)

LOGGER_NAME = "SoAI.mcp.registry.tasks_handlers"


async def _require_task_registry_and_task_for_client(
    manager: MCPTaskHandlerManagerProtocol,
    parameters: JSONDict,
    client_id: str,
) -> tuple[str, TaskRegistryProtocol, Task]:
    if not manager.tasks_enabled:
        raise MCPJSONRPCError(-32601, "Tasks feature is not enabled")
    task_id = extract_task_id_parameter(parameters)
    if not task_id:
        raise MCPJSONRPCError(-32602, "Missing required parameter: taskId")
    task_registry = manager.task.require_task_registry()
    task = await manager.task.require_task_for_client(task_id, client_id)
    return (task_id, task_registry, task)


async def handle_tasks_get(
    manager: MCPTaskHandlerManagerProtocol,
    parameters: JSONDict,
    client_id: str,
) -> JSONDict:
    if not manager.tasks_enabled:
        raise MCPJSONRPCError(-32601, "Tasks feature is not enabled")
    task_id = extract_task_id_parameter(parameters)
    if not task_id:
        raise MCPJSONRPCError(-32602, "Missing required parameter: taskId")
    return build_task_response(await manager.task.require_task_for_client(task_id, client_id))


async def handle_tasks_result(
    manager: MCPTaskHandlerManagerProtocol,
    parameters: JSONDict,
    client_id: str,
) -> JSONDict:
    task_id, task_registry, task = await _require_task_registry_and_task_for_client(
        manager,
        parameters,
        client_id,
    )
    if not task.status.is_terminal():
        await task_registry.wait_for_completion(task_id)
        task = await manager.task.require_task_for_client(task_id, client_id)
    return build_task_response(task)


async def handle_tasks_list(
    manager: MCPTaskHandlerManagerProtocol,
    parameters: JSONDict,
    client_id: str,
) -> JSONDict:
    if not manager.tasks_enabled:
        raise MCPJSONRPCError(-32601, "Tasks feature is not enabled")
    task_registry_queries = manager.task.require_task_registry_queries()
    tasks_for_client = await task_registry_queries.query_by_owner("mcp_client", client_id)
    tasks = [
        {
            "taskId": task_entry.task_id,
            "status": task_entry.status.value,
            "method": (
                method_value
                if isinstance(method_value := task_entry.metadata.get("method"), str)
                else ""
            ),
            "createdAt": timestamp_ms_to_utc_iso(task_entry.created_at_ms),
            "lastUpdatedAt": timestamp_ms_to_utc_iso(task_entry.updated_at_ms),
        }
        for task_entry in tasks_for_client
        if not task_entry.is_expired()
    ]
    cursor_value = parameters.get("cursor")
    cursor = cursor_value if isinstance(cursor_value, str) else None
    page, next_cursor = manager.pagination.paginate_list(tasks, cursor)
    return {"tasks": page, **({"nextCursor": next_cursor} if next_cursor else {})}


async def handle_tasks_cancel(
    manager: MCPTaskHandlerManagerProtocol,
    parameters: JSONDict,
    client_id: str,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    task_id, task_registry, task = await _require_task_registry_and_task_for_client(
        manager,
        parameters,
        client_id,
    )
    if task.status.is_terminal():
        raise MCPJSONRPCError(-32602, f"Cannot cancel terminal task: {task_id}")
    coro = manager.state.task.task_coroutines.pop(task_id, None)
    if coro and (not coro.done()):
        coro.cancel()
    await cancel(task_registry, task_id, reason="Client cancelled task")
    task_or_none = await manager.task.get_task(task_id)
    if task_or_none:
        await manager.task.send_task_status_notification(task_or_none)
    logger.debug("Task %s cancelled by client %s", task_id, client_id)
    return (
        build_task_response(task_or_none)
        if task_or_none
        else {"taskId": task_id, "status": "cancelled"}
    )
