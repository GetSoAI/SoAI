"""SoAI - Calendar reminder repository operations [backend/database/repositories/users/calendar/reminders.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import DatabaseError, ValidationError
from core.timing.epoch import epoch_ms
from core.users.account_identifier_validation import (
    require_calendar_account_id,
    require_calendar_event_id,
    require_calendar_reminder_id,
)
from core.users.account_identifiers import (
    CALENDAR_REMINDER_ID_PREFIX,
    build_random_prefixed_identifier,
)
from core.validation.integers import is_strict_int
from database.core.query_execution import query_to_dicts, sync_fetch_one_as_dict
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.account_validation import (
    optional_epoch_ms,
    require_nonnegative_int,
    require_text,
    require_user_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "read_due_calendar_reminders",
    "sync_delete_calendar_event_reminders",
    "sync_mark_calendar_reminder_delivered",
    "sync_upsert_calendar_reminder",
)


async def read_due_calendar_reminders(
    database: aiosqlite.Connection,
    *,
    due_at_ms: int,
) -> list[SQLiteRowDict]:
    return await query_to_dicts(
        database,
        """
        SELECT *
        FROM calendar_reminders
        WHERE remind_at_ms <= ? AND delivered_at_ms IS NULL AND dismissed_at_ms IS NULL
        ORDER BY remind_at_ms ASC, id ASC
        """,
        (require_nonnegative_int(due_at_ms, "due_at_ms"),),
    )


def sync_upsert_calendar_reminder(conn: sqlite3.Connection, /, payload: JSONDict) -> SQLiteRowDict:
    user_id_value = payload.get("user_id")
    calendar_account_id_value = payload.get("calendar_account_id")
    event_id_value = payload.get("event_id")
    if not is_strict_int(user_id_value):
        raise ValidationError("user_id is invalid.")
    if not isinstance(calendar_account_id_value, str):
        raise ValidationError("account_id is invalid.")
    if not isinstance(event_id_value, str):
        raise ValidationError("event_id is invalid.")
    dedupe_fields = (
        require_user_id(user_id_value),
        require_calendar_account_id(calendar_account_id_value),
        require_calendar_event_id(event_id_value),
        require_text(payload.get("occurrence_key"), "occurrence_key"),
        require_text(payload.get("alarm_key"), "alarm_key"),
        require_text(payload.get("response_state"), "response_state"),
    )
    try:
        cursor = conn.execute(
            """
            SELECT id
            FROM calendar_reminders
            WHERE user_id = ? AND calendar_account_id = ? AND event_id = ? AND occurrence_key = ?
                AND alarm_key = ? AND response_state = ?
            LIMIT 1
            """,
            dedupe_fields,
        )
        existing = sync_fetch_one_as_dict(cursor)
        reminder_id = (
            build_random_prefixed_identifier(CALENDAR_REMINDER_ID_PREFIX)
            if existing is None
            else require_calendar_reminder_id(str(existing.get("id")))
        )
        now_ms = epoch_ms()
        if existing is None:
            conn.execute(
                """
                INSERT INTO calendar_reminders (
                    id, user_id, calendar_account_id, event_id, occurrence_key, alarm_key,
                    response_state, remind_at_ms, due_at_ms, delivered_at_ms, dismissed_at_ms, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reminder_id,
                    dedupe_fields[0],
                    dedupe_fields[1],
                    dedupe_fields[2],
                    dedupe_fields[3],
                    dedupe_fields[4],
                    dedupe_fields[5],
                    require_nonnegative_int(payload.get("remind_at_ms"), "remind_at_ms"),
                    require_nonnegative_int(payload.get("due_at_ms"), "due_at_ms"),
                    optional_epoch_ms(payload.get("delivered_at_ms"), label="delivered_at_ms"),
                    optional_epoch_ms(payload.get("dismissed_at_ms"), label="dismissed_at_ms"),
                    now_ms,
                ),
            )
        else:
            conn.execute(
                """
                UPDATE calendar_reminders
                SET remind_at_ms = ?, due_at_ms = ?, delivered_at_ms = ?, dismissed_at_ms = ?
                WHERE id = ?
                """,
                (
                    require_nonnegative_int(payload.get("remind_at_ms"), "remind_at_ms"),
                    require_nonnegative_int(payload.get("due_at_ms"), "due_at_ms"),
                    optional_epoch_ms(payload.get("delivered_at_ms"), label="delivered_at_ms"),
                    optional_epoch_ms(payload.get("dismissed_at_ms"), label="dismissed_at_ms"),
                    reminder_id,
                ),
            )
        record = sync_fetch_one_as_dict(
            conn.execute("SELECT * FROM calendar_reminders WHERE id = ?", (reminder_id,)),
        )
        if record is None:
            raise DatabaseError("Failed to read calendar reminder.")
        return record
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        raise DatabaseError(
            "Failed to upsert calendar reminder.",
            details={"constraint_type": constraint_type, "detail": detail},
        ) from exception


def sync_mark_calendar_reminder_delivered(
    conn: sqlite3.Connection,
    /,
    reminder_id: str,
    delivered_at_ms: int,
) -> bool:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE calendar_reminders SET delivered_at_ms = ? WHERE id = ?",
            (
                require_nonnegative_int(delivered_at_ms, "delivered_at_ms"),
                require_calendar_reminder_id(reminder_id),
            ),
        )
        return cursor.rowcount > 0
    finally:
        cursor.close()


def sync_delete_calendar_event_reminders(
    conn: sqlite3.Connection,
    /,
    event_id: str,
) -> int:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM calendar_reminders WHERE event_id = ?",
            (require_calendar_event_id(event_id),),
        )
        return max(int(cursor.rowcount), 0)
    finally:
        cursor.close()
