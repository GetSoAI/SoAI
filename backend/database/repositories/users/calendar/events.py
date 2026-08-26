"""SoAI - Calendar event repository operations [backend/database/repositories/users/calendar/events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import DatabaseError
from core.timing.epoch import epoch_ms
from core.users.account_identifier_validation import (
    require_calendar_calendar_id,
    require_calendar_event_id,
)
from core.users.account_identifiers import (
    CALENDAR_EVENT_ID_PREFIX,
    build_random_prefixed_identifier,
)
from core.validation.strings import coerce_optional_trimmed_str
from database.core.query_execution import (
    query_one_to_dict,
    query_to_dicts,
    sync_fetch_one_as_dict,
)
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.account_validation import (
    optional_json_list,
    optional_json_object,
    require_bool_int,
    require_epoch_ms,
    require_nonnegative_int,
    require_text,
    require_user_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "read_calendar_event",
    "read_calendar_events",
    "sync_delete_calendar_event",
    "sync_upsert_calendar_event",
)


async def read_calendar_events(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    calendar_id: str,
) -> list[SQLiteRowDict]:
    return await query_to_dicts(
        database,
        """
        SELECT *
        FROM calendar_events
        WHERE user_id = ? AND calendar_id = ?
        ORDER BY start_at_ms ASC, id ASC
        """,
        (require_user_id(user_id), require_calendar_calendar_id(calendar_id)),
    )


async def read_calendar_event(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    event_id: str,
) -> SQLiteRowDict | None:
    return await query_one_to_dict(
        database,
        "SELECT * FROM calendar_events WHERE user_id = ? AND id = ? LIMIT 1",
        (require_user_id(user_id), require_calendar_event_id(event_id)),
    )


def sync_upsert_calendar_event(
    conn: sqlite3.Connection,
    /,
    user_id: int,
    calendar_id: str,
    payload: JSONDict,
) -> SQLiteRowDict:
    normalized_user_id = require_user_id(user_id)
    normalized_calendar_id = require_calendar_calendar_id(calendar_id)
    remote_href = require_text(payload.get("remote_href"), "remote_href")
    try:
        cursor = conn.execute(
            """
            SELECT id
            FROM calendar_events
            WHERE user_id = ? AND calendar_id = ? AND remote_href = ?
            LIMIT 1
            """,
            (normalized_user_id, normalized_calendar_id, remote_href),
        )
        existing = sync_fetch_one_as_dict(cursor)
        now_ms = epoch_ms()
        row = _build_event_row(payload)
        if existing is None:
            event_id = build_random_prefixed_identifier(CALENDAR_EVENT_ID_PREFIX)
            conn.execute(
                """
                INSERT INTO calendar_events (
                    id, user_id, calendar_id, remote_href, etag, uid, summary, description, location,
                    start_at_ms, end_at_ms, updated_at_ms, timezone, all_day, organizer_json,
                    attendee_count, attendees_json, has_alarms, recurrence_json, alarms_json, raw_ics,
                    created_at_ms, last_modified_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    normalized_user_id,
                    normalized_calendar_id,
                    row["remote_href"],
                    row["etag"],
                    row["uid"],
                    row["summary"],
                    row["description"],
                    row["location"],
                    row["start_at_ms"],
                    row["end_at_ms"],
                    row["updated_at_ms"],
                    row["timezone"],
                    row["all_day"],
                    row["organizer_json"],
                    row["attendee_count"],
                    row["attendees_json"],
                    row["has_alarms"],
                    row["recurrence_json"],
                    row["alarms_json"],
                    row["raw_ics"],
                    now_ms,
                    now_ms,
                ),
            )
            target_event_id = event_id
        else:
            target_event_id = require_calendar_event_id(str(existing.get("id")))
            conn.execute(
                """
                UPDATE calendar_events
                SET etag = ?, uid = ?, summary = ?, description = ?, location = ?, start_at_ms = ?,
                    end_at_ms = ?, updated_at_ms = ?, timezone = ?, all_day = ?, organizer_json = ?,
                    attendee_count = ?, attendees_json = ?, has_alarms = ?, recurrence_json = ?,
                    alarms_json = ?, raw_ics = ?, last_modified_at_ms = ?
                WHERE user_id = ? AND id = ?
                """,
                (
                    row["etag"],
                    row["uid"],
                    row["summary"],
                    row["description"],
                    row["location"],
                    row["start_at_ms"],
                    row["end_at_ms"],
                    row["updated_at_ms"],
                    row["timezone"],
                    row["all_day"],
                    row["organizer_json"],
                    row["attendee_count"],
                    row["attendees_json"],
                    row["has_alarms"],
                    row["recurrence_json"],
                    row["alarms_json"],
                    row["raw_ics"],
                    now_ms,
                    normalized_user_id,
                    target_event_id,
                ),
            )
        record = sync_fetch_one_as_dict(
            conn.execute(
                "SELECT * FROM calendar_events WHERE user_id = ? AND id = ?",
                (normalized_user_id, target_event_id),
            ),
        )
        if record is None:
            raise DatabaseError("Failed to read calendar event.")
        return record
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        raise DatabaseError(
            "Failed to upsert calendar event.",
            details={"constraint_type": constraint_type, "detail": detail},
        ) from exception


def sync_delete_calendar_event(conn: sqlite3.Connection, /, user_id: int, event_id: str) -> bool:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM calendar_events WHERE user_id = ? AND id = ?",
            (require_user_id(user_id), require_calendar_event_id(event_id)),
        )
        return cursor.rowcount > 0
    finally:
        cursor.close()


def _build_event_row(payload: JSONDict) -> dict[str, str | int | None]:
    return {
        "remote_href": require_text(payload.get("remote_href"), "remote_href"),
        "etag": coerce_optional_trimmed_str(payload.get("etag")),
        "uid": coerce_optional_trimmed_str(payload.get("uid")),
        "summary": require_text(payload.get("summary"), "summary"),
        "description": coerce_optional_trimmed_str(payload.get("description")),
        "location": coerce_optional_trimmed_str(payload.get("location")),
        "start_at_ms": require_epoch_ms(payload.get("start_at_ms"), "start_at_ms"),
        "end_at_ms": require_epoch_ms(payload.get("end_at_ms"), "end_at_ms"),
        "updated_at_ms": require_epoch_ms(payload.get("updated_at_ms"), "updated_at_ms"),
        "timezone": coerce_optional_trimmed_str(payload.get("timezone")),
        "all_day": require_bool_int(payload.get("all_day"), "all_day"),
        "organizer_json": optional_json_object(payload.get("organizer")),
        "attendee_count": require_nonnegative_int(payload.get("attendee_count"), "attendee_count"),
        "attendees_json": optional_json_list(payload.get("attendees")),
        "has_alarms": require_bool_int(payload.get("has_alarms"), "has_alarms"),
        "recurrence_json": optional_json_object(payload.get("recurrence")),
        "alarms_json": optional_json_list(payload.get("alarms")),
        "raw_ics": coerce_optional_trimmed_str(payload.get("raw_ics")),
    }
