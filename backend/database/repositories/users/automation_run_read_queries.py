"""SoAI - Automation run read queries [backend/database/repositories/users/automation_run_read_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.automation.automation_constants import AUTOMATION_OCCURRENCES_MAX_ITEMS
from core.errors.exceptions import StateError, ValidationError
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.automation_run_row_formatter import (
    format_automation_run_execution_row,
    format_automation_run_row,
)
from database.repositories.users.automation_run_summary_row_formatter import (
    format_automation_run_summary_row,
)
from database.repositories.users.automation_sql_support import (
    run_select_sql,
    run_summary_select_sql,
)

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "get_automation_run",
    "get_automation_run_for_execution",
    "list_active_automation_run_ids_for_conversation",
    "list_active_automation_runs",
    "list_automation_run_window_records",
    "list_automation_runs",
    "list_automation_runs_for_window",
)


def _format_summary_rows(rows: list[SQLiteRowDict]) -> list[JSONDict]:
    return [
        formatted
        for row in rows
        if row and isinstance((formatted := format_automation_run_summary_row(row)), dict)
    ]


def _list_runs_sql(automation_id: str | None) -> str:
    if automation_id:
        return (
            f"{run_summary_select_sql()} WHERE r.user_id = ? AND r.scheduled_at_ms >= ? "
            "AND r.scheduled_at_ms < ? AND r.automation_id = ? "
            "ORDER BY r.scheduled_at_ms DESC, r.id DESC LIMIT ? OFFSET ?"
        )
    return (
        f"{run_summary_select_sql()} WHERE r.user_id = ? AND r.scheduled_at_ms >= ? "
        "AND r.scheduled_at_ms < ? ORDER BY r.scheduled_at_ms DESC, r.id DESC LIMIT ? OFFSET ?"
    )


def _list_runs_params(
    user_id: int,
    *,
    from_utc_ms: int,
    to_utc_ms: int,
    automation_id: str | None,
    limit: int,
    offset: int,
) -> tuple[str | int | None, ...]:
    if automation_id:
        return (user_id, from_utc_ms, to_utc_ms, automation_id, limit, offset)
    return (user_id, from_utc_ms, to_utc_ms, limit, offset)


async def get_automation_run(
    core: DatabaseCoreProtocol,
    *,
    run_id: str,
    user_id: int,
) -> JSONDict | None:
    async def _query(database: aiosqlite.Connection) -> JSONDict | None:
        row = await query_one_to_dict(
            database,
            f"{run_select_sql()} WHERE r.id = ? AND r.user_id = ?",
            (run_id, user_id),
        )
        formatted = format_automation_run_row(row)
        return formatted if isinstance(formatted, dict) else None

    return await core.reader.execute_read(_query)


async def get_automation_run_for_execution(
    core: DatabaseCoreProtocol,
    *,
    run_id: str,
) -> JSONDict | None:
    async def _query(database: aiosqlite.Connection) -> JSONDict | None:
        row = await query_one_to_dict(
            database,
            f"{run_select_sql()} WHERE r.id = ?",
            (run_id,),
        )
        formatted = format_automation_run_execution_row(row)
        return formatted if isinstance(formatted, dict) else None

    return await core.reader.execute_read(_query)


async def list_active_automation_runs(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
) -> list[JSONDict]:
    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            (
                f"{run_summary_select_sql()} "
                "WHERE r.user_id = ? AND r.status IN ('queued', 'running') "
                "ORDER BY r.scheduled_at_ms DESC, r.id DESC"
            ),
            (user_id,),
        )
        return _format_summary_rows(rows)

    return await core.reader.execute_read(_query)


async def list_automation_runs(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
    from_utc_ms: int,
    to_utc_ms: int,
    automation_id: str | None,
    limit: int,
    offset: int,
) -> list[JSONDict]:
    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            _list_runs_sql(automation_id),
            _list_runs_params(
                user_id,
                from_utc_ms=from_utc_ms,
                to_utc_ms=to_utc_ms,
                automation_id=automation_id,
                limit=limit,
                offset=offset,
            ),
        )
        return _format_summary_rows(rows)

    return await core.reader.execute_read(_query)


async def list_automation_runs_for_window(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
    from_utc_ms: int,
    to_utc_ms: int,
) -> list[JSONDict]:
    return await list_automation_runs(
        core,
        user_id=user_id,
        from_utc_ms=from_utc_ms,
        to_utc_ms=to_utc_ms,
        automation_id=None,
        limit=AUTOMATION_OCCURRENCES_MAX_ITEMS,
        offset=0,
    )


async def list_automation_run_window_records(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
    from_utc_ms: int,
    to_utc_ms: int,
) -> list[JSONDict]:
    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            (
                f"{run_summary_select_sql()} "
                "WHERE r.user_id = ? AND r.scheduled_at_ms >= ? AND r.scheduled_at_ms < ? "
                "ORDER BY r.scheduled_at_ms DESC, r.id DESC"
            ),
            (user_id, from_utc_ms, to_utc_ms),
        )
        return _format_summary_rows(rows)

    return await core.reader.execute_read(_query)


async def list_active_automation_run_ids_for_conversation(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
    conv_id: str,
) -> list[str]:
    normalized_conv_id = conv_id.strip()
    if not normalized_conv_id:
        raise ValidationError("Active automation run lookup requires a conversation id.")

    async def _query(database: aiosqlite.Connection) -> list[str]:
        rows = await query_to_dicts(
            database,
            (
                "SELECT id FROM automation_runs "
                "WHERE user_id = ? AND conv_id = ? AND status IN ('queued', 'running') "
                "ORDER BY scheduled_at_ms DESC, id DESC"
            ),
            (user_id, normalized_conv_id),
        )
        resolved: list[str] = []
        for row in rows:
            candidate = row.get("id")
            if not isinstance(candidate, str) or not candidate.strip():
                raise StateError("Active automation run lookup found an invalid run id.")
            resolved.append(candidate.strip())
        return resolved

    return await core.reader.execute_read(_query)
