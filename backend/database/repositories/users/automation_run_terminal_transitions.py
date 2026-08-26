"""SoAI - Automation run terminal transitions [backend/database/repositories/users/automation_run_terminal_transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.types.json import JSONDict
from database.repositories.users.automation_run_events import (
    enqueue_run_updated_event,
)
from database.repositories.users.automation_run_row_formatter import (
    format_automation_run_row,
)
from database.repositories.users.automation_sql_support import fetch_run_row_by_id

__all__ = (
    "sync_complete_run_abandoned",
    "sync_complete_run_cancelled",
    "sync_complete_run_completed",
    "sync_complete_run_error",
    "sync_complete_run_terminal",
)

if TYPE_CHECKING:
    from typing import Literal

    type AutomationRunTerminalStatus = Literal["completed", "cancelled", "abandoned", "error"]


def sync_complete_run_completed(
    conn: sqlite3.Connection,
    run_id: str,
    user_id: int,
    finished_at_ms: int,
    result_excerpt: str | None,
) -> JSONDict | None:
    return sync_complete_run_terminal(
        conn,
        run_id=run_id,
        user_id=user_id,
        finished_at_ms=finished_at_ms,
        final_status="completed",
        status_message=None,
        result_excerpt=result_excerpt,
    )


def sync_complete_run_cancelled(
    conn: sqlite3.Connection,
    run_id: str,
    user_id: int,
    finished_at_ms: int,
    status_message: str,
    result_excerpt: str | None = None,
) -> JSONDict | None:
    return sync_complete_run_terminal(
        conn,
        run_id=run_id,
        user_id=user_id,
        finished_at_ms=finished_at_ms,
        final_status="cancelled",
        status_message=status_message,
        result_excerpt=result_excerpt,
    )


def sync_complete_run_error(
    conn: sqlite3.Connection,
    run_id: str,
    user_id: int,
    finished_at_ms: int,
    status_message: str,
    result_excerpt: str | None = None,
) -> JSONDict | None:
    return sync_complete_run_terminal(
        conn,
        run_id=run_id,
        user_id=user_id,
        finished_at_ms=finished_at_ms,
        final_status="error",
        status_message=status_message,
        result_excerpt=result_excerpt,
    )


def sync_complete_run_abandoned(
    conn: sqlite3.Connection,
    run_id: str,
    user_id: int,
    finished_at_ms: int,
    status_message: str,
    result_excerpt: str | None = None,
) -> JSONDict | None:
    return sync_complete_run_terminal(
        conn,
        run_id=run_id,
        user_id=user_id,
        finished_at_ms=finished_at_ms,
        final_status="abandoned",
        status_message=status_message,
        result_excerpt=result_excerpt,
    )


def sync_complete_run_terminal(
    conn: sqlite3.Connection,
    run_id: str,
    user_id: int,
    finished_at_ms: int,
    final_status: AutomationRunTerminalStatus,
    status_message: str | None,
    result_excerpt: str | None,
) -> JSONDict | None:
    if final_status not in {"completed", "cancelled", "abandoned", "error"}:
        raise StateError("Automation run terminal status is invalid.")
    resolved_status_message = None if final_status == "completed" else status_message
    if (
        conn.execute(
            (
                "UPDATE automation_runs SET status = ?, finished_at_ms = ?, "
                "status_message = ?, result_excerpt = ? "
                "WHERE id = ? AND user_id = ? AND status = 'running'"
            ),
            (
                final_status,
                finished_at_ms,
                resolved_status_message,
                result_excerpt,
                run_id,
                user_id,
            ),
        ).rowcount
        != 1
    ):
        return None
    formatted = format_automation_run_row(fetch_run_row_by_id(conn, run_id=run_id, user_id=user_id))
    if not isinstance(formatted, dict):
        return None
    enqueue_run_updated_event(
        conn,
        formatted=formatted,
        created_at_ms=finished_at_ms,
        run_id=run_id,
    )
    return formatted
