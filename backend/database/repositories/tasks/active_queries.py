"""SoAI - Active unified task query operations [backend/database/repositories/tasks/active_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.tasks.cancellation_ids import SYSTEM_CANCELLATION_ID_PREFIX
from core.tasks.status_policy import ACTIVE_TASK_STATUS_VALUES, active_task_status_placeholders
from database.core.query_execution import query_to_dicts
from database.repositories.tasks.task_rows import format_unified_task_row

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = ()


async def query_active_tasks_for_cancellation_id_keyset_query(
    database: aiosqlite.Connection,
    cancellation_id: str,
    *,
    after_created_at_ms: int,
    after_task_id: str,
    limit: int,
) -> list[JSONDict]:
    placeholders = active_task_status_placeholders()
    rows = await query_to_dicts(
        database,
        f"""
        SELECT * FROM unified_tasks
        WHERE status IN ({placeholders})
          AND cancellation_id = ?
          AND (
                created_at_ms > ?
                OR (created_at_ms = ? AND task_id > ?)
              )
        ORDER BY created_at_ms ASC, task_id ASC
        LIMIT ?
        """,
        (
            *ACTIVE_TASK_STATUS_VALUES,
            cancellation_id,
            int(after_created_at_ms),
            int(after_created_at_ms),
            after_task_id,
            int(limit),
        ),
    )
    return [formatted for row in rows if (formatted := format_unified_task_row(row))]


async def query_active_tasks_by_type_keyset_query(
    database: aiosqlite.Connection,
    task_type: str,
    *,
    after_created_at_ms: int,
    after_task_id: str,
    limit: int,
) -> list[JSONDict]:
    placeholders = active_task_status_placeholders()
    rows = await query_to_dicts(
        database,
        f"""
        SELECT * FROM unified_tasks
        WHERE status IN ({placeholders})
          AND task_type = ?
          AND (
                created_at_ms > ?
                OR (created_at_ms = ? AND task_id > ?)
              )
        ORDER BY created_at_ms ASC, task_id ASC
        LIMIT ?
        """,
        (
            *ACTIVE_TASK_STATUS_VALUES,
            task_type,
            int(after_created_at_ms),
            int(after_created_at_ms),
            after_task_id,
            int(limit),
        ),
    )
    return [formatted for row in rows if (formatted := format_unified_task_row(row))]


async def query_active_cancellation_ids_query(
    database: aiosqlite.Connection,
    *,
    include_internal: bool,
    limit: int,
) -> list[str]:
    placeholders = active_task_status_placeholders()
    system_prefix = SYSTEM_CANCELLATION_ID_PREFIX
    internal_clause = (
        ""
        if include_internal
        else ("AND substr(cancellation_id, 1, " f"{len(system_prefix)}) != '{system_prefix}'")
    )
    rows = await query_to_dicts(
        database,
        f"""
        SELECT DISTINCT cancellation_id
        FROM unified_tasks
        WHERE status IN ({placeholders})
          AND cancellation_requested_at_ms IS NULL
          AND cancellation_id IS NOT NULL
          AND trim(cancellation_id) != ''
          {internal_clause}
        ORDER BY cancellation_id ASC
        LIMIT ?
        """,
        (*ACTIVE_TASK_STATUS_VALUES, int(limit)),
    )
    cancellation_ids: list[str] = []
    for row in rows:
        value = row.get("cancellation_id")
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                cancellation_ids.append(normalized)
    return cancellation_ids


async def query_stuck_active_tasks_query(
    database: aiosqlite.Connection,
    cutoff_epoch_ms: int,
    exclude_owner_types: tuple[str, ...],
    exclude_task_types: tuple[str, ...],
    limit: int,
    *,
    after_updated_at_ms: int | None = None,
    after_task_id: str | None = None,
) -> list[JSONDict]:
    if (after_updated_at_ms is None) != (after_task_id is None):
        raise ValidationError("Stale task keyset cursor fields must be provided together.")
    active_placeholders = active_task_status_placeholders()
    exclude_owner_type_placeholders = (
        ", ".join(("?",) * len(exclude_owner_types)) if exclude_owner_types else ""
    )
    exclusion_clause = (
        f"AND owner_type NOT IN ({exclude_owner_type_placeholders})" if exclude_owner_types else ""
    )
    exclude_task_type_placeholders = (
        ", ".join(("?",) * len(exclude_task_types)) if exclude_task_types else ""
    )
    task_type_exclusion_clause = (
        f"AND task_type NOT IN ({exclude_task_type_placeholders})" if exclude_task_types else ""
    )
    cursor_clause = (
        "AND (updated_at_ms > ? OR (updated_at_ms = ? AND task_id > ?))"
        if after_updated_at_ms is not None
        else ""
    )
    query = f"""
        SELECT * FROM unified_tasks
        WHERE status IN ({active_placeholders})
        AND updated_at_ms < ?
        AND orchestration_state IS NULL
        AND cancellation_requested_at_ms IS NULL
        AND NOT EXISTS (
            SELECT 1 FROM mutation_admissions
            WHERE accepted_task_id = unified_tasks.task_id
              AND lifecycle_status IN ('accepted', 'running', 'recovery_required')
        )
        {exclusion_clause}
        {task_type_exclusion_clause}
        {cursor_clause}
        ORDER BY updated_at_ms ASC, task_id ASC
        LIMIT ?
    """
    params: list[SQLiteValue] = list(ACTIVE_TASK_STATUS_VALUES)
    params.append(cutoff_epoch_ms)
    if exclude_owner_types:
        params.extend(exclude_owner_types)
    if exclude_task_types:
        params.extend(exclude_task_types)
    if after_updated_at_ms is not None and after_task_id is not None:
        params.extend((after_updated_at_ms, after_updated_at_ms, after_task_id))
    params.append(limit)
    rows = await query_to_dicts(database, query, tuple(params))
    return [formatted for row in rows if (formatted := format_unified_task_row(row))]


async def query_prefetched_orchestrated_task_ids_query(
    database: aiosqlite.Connection,
    *,
    limit: int,
) -> list[str]:
    rows = await query_to_dicts(
        database,
        f"""
        SELECT ut.task_id
          FROM unified_tasks AS ut
          JOIN orchestrator_queue_items AS oq ON oq.task_id = ut.task_id
         WHERE ut.status IN ({active_task_status_placeholders()})
           AND ut.cancellation_requested_at_ms IS NULL
           AND oq.phase = 'prefetched'
         ORDER BY oq.enqueue_seq ASC
         LIMIT ?
        """,
        (*ACTIVE_TASK_STATUS_VALUES, int(limit)),
    )
    return [
        str(task_id_value)
        for row in rows
        if isinstance((task_id_value := row.get("task_id")), str) and task_id_value
    ]
