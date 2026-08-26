"""SoAI - Unified task query operations with filters and formatting [backend/database/repositories/tasks/queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.database.task_requests import UnifiedTaskQueryRequest
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.tasks.filters import (
    build_unified_tasks_where_clause,
)
from database.repositories.tasks.task_rows import format_unified_task_row

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ()


async def query_unified_tasks_query(
    database: aiosqlite.Connection,
    request: UnifiedTaskQueryRequest,
) -> list[JSONDict]:
    where_clause, params = build_unified_tasks_where_clause(
        user_id=request.user_id,
        status=request.status,
        task_type=request.task_type,
        owner_type=request.owner_type,
        owner_id=request.owner_id,
        cancellation_id=request.cancellation_id,
        active_only=request.active_only,
        exclude_cancellation_requested=request.exclude_cancellation_requested,
    )
    params.extend([request.limit, request.offset])
    rows = await query_to_dicts(
        database,
        f"""
        SELECT *
          FROM unified_tasks
         WHERE {where_clause}
         ORDER BY updated_at_ms DESC
         LIMIT ? OFFSET ?
        """,
        tuple(params),
    )
    return [formatted for row in rows if (formatted := format_unified_task_row(row))]


async def get_unified_task_query(database: aiosqlite.Connection, task_id: str) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        "SELECT * FROM unified_tasks WHERE task_id = ?",
        (task_id,),
    )
    return format_unified_task_row(row)


async def get_unified_tasks_by_ids_query(
    database: aiosqlite.Connection,
    task_ids: tuple[str, ...],
) -> list[JSONDict]:
    if not task_ids:
        return []
    placeholders = ", ".join("?" for _ in task_ids)
    rows = await query_to_dicts(
        database,
        f"SELECT * FROM unified_tasks WHERE task_id IN ({placeholders})",
        task_ids,
    )
    rows_by_task_id: dict[str, JSONDict] = {}
    for row in rows:
        formatted = format_unified_task_row(row)
        if formatted is None:
            continue
        task_id = formatted.get("task_id")
        if isinstance(task_id, str) and task_id:
            rows_by_task_id[task_id] = formatted
    return [rows_by_task_id[task_id] for task_id in task_ids if task_id in rows_by_task_id]
