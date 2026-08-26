"""SoAI - Unified task visibility queries [backend/database/repositories/tasks/visibility_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.types.json import JSONDict
from database.core.query_execution import query_to_dicts
from database.repositories.tasks.filters import (
    build_unified_tasks_visible_to_user_where_clause,
)
from database.repositories.tasks.task_rows import format_unified_task_row

__all__ = (
    "query_unified_tasks_visible_to_user_query",
    "query_unified_tasks_visible_to_user_with_count_query",
)


async def query_unified_tasks_visible_to_user_query(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    include_system: bool,
    task_type: str | None = None,
    active_only: bool = False,
    exclude_cancellation_requested: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[JSONDict]:
    where_clause, params = build_unified_tasks_visible_to_user_where_clause(
        user_id=user_id,
        include_system=include_system,
        task_type=task_type,
        active_only=active_only,
        exclude_cancellation_requested=exclude_cancellation_requested,
    )
    params.extend([int(limit), int(offset)])
    rows = await query_to_dicts(
        database,
        f"SELECT * FROM unified_tasks WHERE {where_clause} ORDER BY updated_at_ms DESC LIMIT ? OFFSET ?",
        tuple(params),
    )
    return [formatted for row in rows if (formatted := format_unified_task_row(row))]


async def query_unified_tasks_visible_to_user_with_count_query(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    include_system: bool,
    task_type: str | None = None,
    active_only: bool = False,
    exclude_cancellation_requested: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[JSONDict], int]:
    where_clause, params = build_unified_tasks_visible_to_user_where_clause(
        user_id=user_id,
        include_system=include_system,
        task_type=task_type,
        active_only=active_only,
        exclude_cancellation_requested=exclude_cancellation_requested,
    )
    rows = await query_to_dicts(
        database,
        f"""
        WITH filtered_tasks AS (
            SELECT * FROM unified_tasks WHERE {where_clause}
        ),
        paged_tasks AS (
            SELECT * FROM filtered_tasks ORDER BY updated_at_ms DESC LIMIT ? OFFSET ?
        ),
        total_count AS (
            SELECT COUNT(*) AS total_count FROM filtered_tasks
        )
        SELECT paged_tasks.*, total_count.total_count
        FROM total_count
        LEFT JOIN paged_tasks ON 1=1
        ORDER BY paged_tasks.updated_at_ms DESC
        """,
        (*params, int(limit), int(offset)),
    )
    if not rows:
        return ([], 0)
    total_count = 0
    formatted_rows: list[JSONDict] = []
    for row in rows:
        total_count_value = row.get("total_count")
        if isinstance(total_count_value, int) and (not isinstance(total_count_value, bool)):
            total_count = int(total_count_value)
        task_id_value = row.get("task_id")
        if not isinstance(task_id_value, str) or not task_id_value:
            continue
        task_row = dict(row)
        task_row.pop("total_count", None)
        formatted = format_unified_task_row(task_row)
        if formatted is not None:
            formatted_rows.append(formatted)
    return (formatted_rows, total_count)
