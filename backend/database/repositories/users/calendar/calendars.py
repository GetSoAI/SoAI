"""SoAI - Calendar record read and upsert operations [backend/database/repositories/users/calendar/calendars.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import DatabaseError
from core.timing.epoch import epoch_ms
from core.users.account_identifier_validation import (
    require_calendar_account_id,
    require_calendar_calendar_id,
)
from core.users.account_identifiers import (
    CALENDAR_CALENDAR_ID_PREFIX,
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
    require_bool_int,
    require_text,
    require_user_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "read_calendar",
    "read_calendar_by_remote_href",
    "read_calendars",
    "sync_upsert_calendar",
)


async def read_calendars(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    account_id: str,
) -> list[SQLiteRowDict]:
    return await query_to_dicts(
        database,
        """
        SELECT *
        FROM calendar_calendars
        WHERE user_id = ? AND calendar_account_id = ?
        ORDER BY name COLLATE NOCASE ASC, id ASC
        """,
        (require_user_id(user_id), require_calendar_account_id(account_id)),
    )


async def read_calendar(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    calendar_id: str,
) -> SQLiteRowDict | None:
    return await query_one_to_dict(
        database,
        "SELECT * FROM calendar_calendars WHERE user_id = ? AND id = ? LIMIT 1",
        (require_user_id(user_id), require_calendar_calendar_id(calendar_id)),
    )


async def read_calendar_by_remote_href(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    account_id: str,
    remote_href: str,
) -> SQLiteRowDict | None:
    return await query_one_to_dict(
        database,
        """
        SELECT *
        FROM calendar_calendars
        WHERE user_id = ? AND calendar_account_id = ? AND remote_href = ?
        LIMIT 1
        """,
        (
            require_user_id(user_id),
            require_calendar_account_id(account_id),
            require_text(remote_href, "remote_href"),
        ),
    )


def sync_upsert_calendar(
    conn: sqlite3.Connection,
    /,
    user_id: int,
    account_id: str,
    payload: JSONDict,
) -> SQLiteRowDict:
    normalized_user_id = require_user_id(user_id)
    normalized_account_id = require_calendar_account_id(account_id)
    remote_href = require_text(payload.get("remote_href"), "remote_href")
    try:
        cursor = conn.execute(
            """
            SELECT id
            FROM calendar_calendars
            WHERE user_id = ? AND calendar_account_id = ? AND remote_href = ?
            LIMIT 1
            """,
            (normalized_user_id, normalized_account_id, remote_href),
        )
        existing = sync_fetch_one_as_dict(cursor)
        now_ms = epoch_ms()
        if existing is None:
            calendar_id = build_random_prefixed_identifier(CALENDAR_CALENDAR_ID_PREFIX)
            conn.execute(
                """
                INSERT INTO calendar_calendars (
                    id, user_id, calendar_account_id, remote_href, sync_token, etag, name, color,
                    timezone, read_only, created_at_ms, last_modified_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    calendar_id,
                    normalized_user_id,
                    normalized_account_id,
                    remote_href,
                    coerce_optional_trimmed_str(payload.get("sync_token")),
                    coerce_optional_trimmed_str(payload.get("etag")),
                    require_text(payload.get("name"), "name"),
                    coerce_optional_trimmed_str(payload.get("color")),
                    coerce_optional_trimmed_str(payload.get("timezone")),
                    require_bool_int(payload.get("read_only"), "read_only"),
                    now_ms,
                    now_ms,
                ),
            )
            target_calendar_id = calendar_id
        else:
            target_calendar_id = require_calendar_calendar_id(str(existing.get("id")))
            conn.execute(
                """
                UPDATE calendar_calendars
                SET sync_token = ?, etag = ?, name = ?, color = ?, timezone = ?, read_only = ?, last_modified_at_ms = ?
                WHERE user_id = ? AND id = ?
                """,
                (
                    coerce_optional_trimmed_str(payload.get("sync_token")),
                    coerce_optional_trimmed_str(payload.get("etag")),
                    require_text(payload.get("name"), "name"),
                    coerce_optional_trimmed_str(payload.get("color")),
                    coerce_optional_trimmed_str(payload.get("timezone")),
                    require_bool_int(payload.get("read_only"), "read_only"),
                    now_ms,
                    normalized_user_id,
                    target_calendar_id,
                ),
            )
        record = sync_fetch_one_as_dict(
            conn.execute(
                "SELECT * FROM calendar_calendars WHERE user_id = ? AND id = ?",
                (normalized_user_id, target_calendar_id),
            ),
        )
        if record is None:
            raise DatabaseError("Failed to read calendar.")
        return record
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        raise DatabaseError(
            "Failed to upsert calendar.",
            details={"constraint_type": constraint_type, "detail": detail},
        ) from exception
