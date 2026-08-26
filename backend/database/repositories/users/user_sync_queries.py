"""SoAI - User sync query helpers [backend/database/repositories/users/user_sync_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.users.account_types import HUMAN_ACCOUNT_TYPE
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row
from database.repositories.users.user_row_normalization import normalize_user_row

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_count_human_admins",
    "sync_get_account_by_id",
    "sync_get_human_user_by_id",
)


def sync_get_account_by_id(conn: sqlite3.Connection, user_id: int) -> JSONDict | None:
    cursor = conn.execute("SELECT * FROM webui_users WHERE id = ?", (user_id,))
    return normalize_user_row(sync_fetch_one_as_dict(cursor))


def sync_get_human_user_by_id(conn: sqlite3.Connection, user_id: int) -> JSONDict | None:
    cursor = conn.execute(
        "SELECT * FROM webui_users WHERE id = ? AND account_type = ?",
        (user_id, HUMAN_ACCOUNT_TYPE),
    )
    return normalize_user_row(sync_fetch_one_as_dict(cursor))


def sync_count_human_admins(conn: sqlite3.Connection) -> int:
    row = sync_fetch_one_as_dict(
        conn.execute("""
            SELECT COUNT(*) AS count
            FROM webui_users
            WHERE account_type = 'human' AND is_admin = 1
            """),
    )
    if not row:
        return 0
    count_value = coerce_required_int_from_sqlite_row(row, "count")
    if count_value < 0:
        raise StateError("Admin count query returned an invalid value.")
    return int(count_value)
