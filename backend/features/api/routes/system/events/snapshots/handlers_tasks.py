"""SoAI - Snapshot handlers for task-related resources [backend/features/api/routes/system/events/snapshots/handlers_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import WebSocket

from core.errors.exceptions import SecurityError
from core.tasks.api_queries import (
    build_task_visibility_user_payload,
    get_task_visibility_error,
    parse_task_type_filter_value,
    query_active_tasks_for_user,
    task_to_response,
)
from core.tasks.identifiers import require_task_id
from core.tasks.list_limits import resolve_task_list_limits
from features.api.runtime.task_registry import require_task_registry_or_raise
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "snapshot_tasks_active",
    "snapshot_tasks_by_id",
)


async def snapshot_tasks_active(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    api_context = connection.api_context
    registry_queries = api_context.dependencies.task_registry_queries
    task_type_str = data.get("task_type")
    task_type_filter = parse_task_type_filter_value(
        task_type_str if isinstance(task_type_str, str) else None,
        registry_queries.task_catalog,
    )
    task_list_limits = resolve_task_list_limits(api_context.dependencies.config)
    effective_limit = min(task_list_limits.max_limit, task_list_limits.default_limit)
    user_payload = build_task_visibility_user_payload(connection.user)
    tasks, total_count = await query_active_tasks_for_user(
        user_id=user_payload["id"],
        is_admin=user_payload["is_admin"],
        task_type_filter=task_type_filter,
        effective_limit=effective_limit,
        registry=registry_queries,
    )
    return {
        "tasks": [task_to_response(task).model_dump() for task in tasks],
        "total_count": total_count,
    }


async def snapshot_tasks_by_id(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    normalized = require_task_id(
        data.get("task_id"),
        error_message="tasks.by_id snapshot requires task_id",
    )
    api_context = connection.api_context
    registry = await require_task_registry_or_raise(connection.request, api_context.dependencies)
    task = await registry.get(normalized, force_refresh=True)
    if task is None:
        return None
    visibility_error = get_task_visibility_error(
        task,
        build_task_visibility_user_payload(connection.user),
    )
    if visibility_error:
        raise SecurityError(visibility_error, details={"task_id": normalized})
    return task_to_response(task).model_dump()
