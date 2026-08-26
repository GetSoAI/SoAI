"""SoAI - Automation read queries [backend/database/repositories/users/automation_read_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.validation.integers import is_strict_int
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.automation_row_formatter import (
    format_automation_row,
    format_automation_window_source_row,
)
from database.repositories.users.automation_sql_support import automation_select_sql

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "get_automation",
    "has_active_runs",
    "list_automations",
    "list_due_automations",
    "list_enabled_automation_window_sources",
    "list_enabled_automations",
)


def _normalize_list_limit(limit: int) -> int:
    if not is_strict_int(limit):
        raise ValidationError("Automation list limit must be an integer.")
    if limit <= 0:
        raise ValidationError("Automation list limit must be positive.")
    return limit


def _normalize_list_offset(offset: int) -> int:
    if not is_strict_int(offset):
        raise ValidationError("Automation list offset must be an integer.")
    if offset < 0:
        raise ValidationError("Automation list offset must be non-negative.")
    return offset


def _format_automation_rows(rows: list[SQLiteRowDict]) -> list[JSONDict]:
    return [
        formatted
        for row in rows
        if row and isinstance((formatted := format_automation_row(row)), dict)
    ]


async def get_automation(
    core: DatabaseCoreProtocol,
    *,
    automation_id: str,
    user_id: int,
) -> JSONDict | None:
    async def _query(database: aiosqlite.Connection) -> JSONDict | None:
        row = await query_one_to_dict(
            database,
            f"{automation_select_sql()} WHERE id = ? AND user_id = ?",
            (automation_id, user_id),
        )
        formatted = format_automation_row(row)
        return formatted if isinstance(formatted, dict) else None

    return await core.reader.execute_read(_query)


async def list_automations(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
    limit: int,
    offset: int,
) -> tuple[list[JSONDict], bool]:
    resolved_limit = _normalize_list_limit(limit)
    resolved_offset = _normalize_list_offset(offset)

    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            f"{automation_select_sql()} WHERE user_id = ? ORDER BY last_modified_at_ms DESC, id ASC LIMIT ? OFFSET ?",
            (user_id, resolved_limit + 1, resolved_offset),
        )
        return _format_automation_rows(rows)

    records = await core.reader.execute_read(_query)
    has_more = len(records) > resolved_limit
    return (records[:resolved_limit], has_more)


async def list_enabled_automations(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
) -> list[JSONDict]:
    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            f"{automation_select_sql()} WHERE user_id = ? AND enabled = 1 ORDER BY id ASC",
            (user_id,),
        )
        return _format_automation_rows(rows)

    return await core.reader.execute_read(_query)


async def list_enabled_automation_window_sources(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
) -> list[JSONDict]:
    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            """
            SELECT id, title, enabled, color, timezone, start_local, recurrence
            FROM automations
            WHERE user_id = ? AND enabled = 1
            ORDER BY id ASC
            """,
            (user_id,),
        )
        return [
            formatted
            for row in rows
            if row and isinstance((formatted := format_automation_window_source_row(row)), dict)
        ]

    return await core.reader.execute_read(_query)


async def list_due_automations(
    core: DatabaseCoreProtocol,
    *,
    now_ms: int,
    limit: int,
) -> list[JSONDict]:
    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            f"{automation_select_sql()} WHERE enabled = 1 AND next_run_at_ms IS NOT NULL AND next_run_at_ms <= ? ORDER BY next_run_at_ms ASC, id ASC LIMIT ?",
            (now_ms, limit),
        )
        return _format_automation_rows(rows)

    return await core.reader.execute_read(_query)


async def has_active_runs(
    core: DatabaseCoreProtocol,
    *,
    automation_id: str,
    user_id: int,
) -> bool:
    async def _query(database: aiosqlite.Connection) -> bool:
        row = await query_one_to_dict(
            database,
            """
            SELECT 1
            FROM automation_runs
            WHERE automation_id = ? AND user_id = ? AND status IN ('queued', 'running')
            LIMIT 1
            """,
            (automation_id, user_id),
        )
        return row is not None

    return await core.reader.execute_read(_query)
