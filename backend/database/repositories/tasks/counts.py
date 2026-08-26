"""SoAI - Database tasks count operations [backend/database/repositories/tasks/counts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.tasks.status_policy import (
    ACTIVE_TASK_STATUS_VALUES,
    RUNNING_TASK_STATUS_VALUES,
    active_task_status_placeholders,
    running_task_status_placeholders,
)
from core.tasks.type_catalog import orchestrated_inference_task_type_values
from database.core.query_execution import query_one_to_dict
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row
from database.repositories.tasks.filters import (
    build_unified_tasks_visible_to_user_where_clause,
    build_unified_tasks_where_clause,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "build_unified_task_count",
    "count_active_unified_tasks_query",
    "count_running_orchestrated_inference_tasks_for_owner_query",
    "count_unified_tasks_visible_to_user_query",
)


def _count_from_row(row: SQLiteRowDict | None) -> int:
    if row is None:
        return 0
    return coerce_required_int_from_sqlite_row(row, "count")


async def count_active_unified_tasks_query(
    database: aiosqlite.Connection,
    owner_type: str,
    owner_id: str,
) -> int:
    row = await query_one_to_dict(
        database,
        f"""
        SELECT COUNT(*) AS count FROM unified_tasks
        WHERE owner_type = ?
          AND owner_id = ?
          AND status IN ({active_task_status_placeholders()})
          AND cancellation_requested_at_ms IS NULL
        """,
        (owner_type, owner_id, *ACTIVE_TASK_STATUS_VALUES),
    )
    return _count_from_row(row)


async def count_running_orchestrated_inference_tasks_for_owner_query(
    database: aiosqlite.Connection,
    owner_type: str,
    owner_id: str,
) -> int:
    task_type_values = orchestrated_inference_task_type_values()
    task_type_placeholders = ", ".join("?" * len(task_type_values))
    row = await query_one_to_dict(
        database,
        f"""
        SELECT COUNT(*) AS count FROM unified_tasks
        WHERE owner_type = ? AND owner_id = ?
          AND task_type IN ({task_type_placeholders})
          AND status IN ({running_task_status_placeholders()})
          AND cancellation_requested_at_ms IS NULL
        """,
        (
            owner_type,
            owner_id,
            *task_type_values,
            *RUNNING_TASK_STATUS_VALUES,
        ),
    )
    return _count_from_row(row)


async def count_unified_tasks_visible_to_user_query(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    include_system: bool,
    task_type: str | None = None,
    active_only: bool = False,
    exclude_cancellation_requested: bool = False,
) -> int:
    where_clause, params = build_unified_tasks_visible_to_user_where_clause(
        user_id=user_id,
        include_system=include_system,
        task_type=task_type,
        active_only=active_only,
        exclude_cancellation_requested=exclude_cancellation_requested,
    )
    row = await query_one_to_dict(
        database,
        f"SELECT COUNT(*) AS count FROM unified_tasks WHERE {where_clause}",
        tuple(params),
    )
    return _count_from_row(row)


async def build_unified_task_count(
    database: aiosqlite.Connection,
    *,
    user_id: int | None = None,
    status: str | None = None,
    task_type: str | None = None,
    owner_type: str | None = None,
    owner_id: str | None = None,
    cancellation_id: str | None = None,
    active_only: bool = False,
    exclude_cancellation_requested: bool = False,
) -> int:
    where_clause, params = build_unified_tasks_where_clause(
        user_id=user_id,
        status=status,
        task_type=task_type,
        owner_type=owner_type,
        owner_id=owner_id,
        cancellation_id=cancellation_id,
        active_only=active_only,
        exclude_cancellation_requested=exclude_cancellation_requested,
    )
    row = await query_one_to_dict(
        database,
        f"SELECT COUNT(*) AS count FROM unified_tasks WHERE {where_clause}",
        tuple(params),
    )
    return _count_from_row(row)
