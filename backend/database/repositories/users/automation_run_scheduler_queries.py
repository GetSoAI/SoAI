"""SoAI - Automation run scheduler queries [backend/database/repositories/users/automation_run_scheduler_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.users.user_id import is_strict_user_id
from core.validation.integers import is_strict_int
from database.core.query_execution import query_to_dicts

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol
    from core.types.json import JSONDict

__all__ = (
    "count_active_automation_runs_by_user",
    "list_queued_automation_run_ids",
    "list_running_automation_run_summaries",
)


async def count_active_automation_runs_by_user(
    core: DatabaseCoreProtocol,
) -> dict[int, int]:
    async def _query(database: aiosqlite.Connection) -> dict[int, int]:
        rows = await query_to_dicts(
            database,
            (
                "SELECT user_id, COUNT(1) AS run_count "
                "FROM automation_runs "
                "WHERE status IN ('queued', 'running') "
                "GROUP BY user_id"
            ),
            (),
        )
        counts: dict[int, int] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            user_id_value = row.get("user_id")
            run_count_value = row.get("run_count")
            if not is_strict_user_id(user_id_value):
                raise ValidationError("Active automation run count user_id is invalid.")
            if not is_strict_int(run_count_value):
                raise ValidationError("Active automation run count is invalid.")
            if run_count_value < 0:
                raise ValidationError("Active automation run count row is invalid.")
            counts[int(user_id_value)] = int(run_count_value)
        return counts

    return await core.reader.execute_read(_query)


async def list_queued_automation_run_ids(core: DatabaseCoreProtocol) -> list[str]:
    async def _query(database: aiosqlite.Connection) -> list[str]:
        rows = await query_to_dicts(
            database,
            "SELECT id FROM automation_runs WHERE status = 'queued' ORDER BY scheduled_at_ms ASC, id ASC",
        )
        run_ids: list[str] = []
        for row in rows:
            run_id = row.get("id")
            if isinstance(run_id, str):
                run_ids.append(run_id)
        return run_ids

    return await core.reader.execute_read(_query)


async def list_running_automation_run_summaries(
    core: DatabaseCoreProtocol,
    *,
    limit: int,
) -> list[JSONDict]:
    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            (
                "SELECT id AS run_id, user_id, owner_task_id, scheduled_at_ms AS scheduled_at_ms, "
                "started_at_ms AS started_at_actual_ms, status "
                "FROM automation_runs "
                "WHERE status = 'running' "
                "ORDER BY scheduled_at_ms ASC, id ASC "
                "LIMIT ?"
            ),
            (int(limit),),
        )
        summaries: list[JSONDict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            run_id_value = row.get("run_id")
            user_id_value = row.get("user_id")
            owner_task_id_value = row.get("owner_task_id")
            scheduled_at_ms_value = row.get("scheduled_at_ms")
            started_at_actual_ms_value = row.get("started_at_actual_ms")
            status_value = row.get("status")
            if not isinstance(run_id_value, str) or not run_id_value.strip():
                raise ValidationError("Automation run summary run_id is missing or invalid.")
            if not is_strict_user_id(user_id_value):
                raise ValidationError("Automation run summary user_id is missing or invalid.")
            if owner_task_id_value is not None and not isinstance(owner_task_id_value, str):
                raise ValidationError("Automation run summary owner_task_id is invalid.")
            if (
                isinstance(scheduled_at_ms_value, bool)
                or not isinstance(scheduled_at_ms_value, int)
                or scheduled_at_ms_value < 1
            ):
                raise ValidationError(
                    "Automation run summary scheduled_at_ms is missing or invalid.",
                )
            if started_at_actual_ms_value is not None and (
                isinstance(started_at_actual_ms_value, bool)
                or not isinstance(started_at_actual_ms_value, int)
                or started_at_actual_ms_value < 1
            ):
                raise ValidationError("Automation run summary started_at_actual_ms is invalid.")
            if not isinstance(status_value, str) or not status_value.strip():
                raise ValidationError("Automation run summary status is missing or invalid.")
            summaries.append(
                {
                    "run_id": run_id_value.strip(),
                    "user_id": int(user_id_value),
                    "owner_task_id": owner_task_id_value,
                    "scheduled_at_ms": int(scheduled_at_ms_value),
                    "started_at_actual_ms": started_at_actual_ms_value,
                    "status": status_value.strip(),
                },
            )
        return summaries

    return await core.reader.execute_read(_query)
