"""SoAI - Notification creation sync database operations [backend/database/repositories/users/notifications_sync_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pydantic

from core.errors.exceptions import StateError, ValidationError
from core.notifications.notification_contracts import NOTIFICATION_TYPE_SQL_VALUES
from core.notifications.notification_record_models import NotificationLink
from core.notifications.notification_text_models import parse_notification_text_db
from core.serialization.json_parsing import parse_json_value
from core.users.user_id import is_strict_user_id
from database.core.query_execution import (
    sync_fetch_all_as_dicts,
    sync_fetch_one_as_dict,
)
from database.core.sqlite_numbers import (
    coerce_required_int_from_sqlite_row,
    coerce_required_nonempty_str_from_sqlite_row,
)
from database.repositories.users.notifications_event_outbox import (
    sync_enqueue_notification_created_domain_event,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("sync_create_notification",)


def _sync_require_valid_notification_text(value: str, *, label: str) -> None:
    try:
        parse_notification_text_db(value)
    except ValueError as exception:
        raise StateError(f"Notification {label} payload is invalid.") from exception


def _sync_require_valid_link_json(value: str) -> None:
    if not value:
        raise StateError("Notification link_json is invalid.")
    try:
        decoded = parse_json_value(value)
    except ValidationError as exception:
        raise StateError("Notification link_json is invalid.") from exception
    if not isinstance(decoded, dict):
        raise StateError("Notification link_json is invalid.")
    try:
        NotificationLink.model_validate(decoded)
    except pydantic.ValidationError as exception:
        raise StateError("Notification link_json is invalid.") from exception


def _sync_count_notifications(conn: sqlite3.Connection, *, user_id: int) -> int:
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT COUNT(*) AS count FROM webui_notifications WHERE user_id = ?",
            (int(user_id),),
        ),
    )
    if not row:
        return 0
    value = coerce_required_int_from_sqlite_row(row, "count")
    if value < 0:
        raise StateError("Notification count query returned invalid result.")
    return int(value)


def _sync_delete_notification_ids(conn: sqlite3.Connection, ids: list[str]) -> int:
    if not ids:
        return 0
    placeholders = ", ".join("?" for _ in ids)
    cursor = conn.execute(
        f"DELETE FROM webui_notifications WHERE id IN ({placeholders})",
        tuple(ids),
    )
    return int(cursor.rowcount or 0)


def _sync_prune_notifications(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    max_per_user: int,
    protected_notification_id: str,
) -> None:
    resolved_max = max(int(max_per_user) or 1, 1)
    current_count = _sync_count_notifications(conn, user_id=int(user_id))
    if current_count <= resolved_max:
        return
    to_delete = current_count - resolved_max
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            """
            SELECT id
            FROM webui_notifications
            WHERE user_id = ? AND read_at_ms IS NOT NULL AND id != ?
            ORDER BY read_at_ms ASC, created_at_ms ASC, id ASC
            LIMIT ?
            """,
            (int(user_id), protected_notification_id, int(to_delete)),
        ),
    )
    read_ids = [coerce_required_nonempty_str_from_sqlite_row(row, "id") for row in rows]
    deleted_read = _sync_delete_notification_ids(conn, read_ids)
    if deleted_read:
        current_count = _sync_count_notifications(conn, user_id=int(user_id))
        if current_count <= resolved_max:
            return
        to_delete = current_count - resolved_max
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            """
            SELECT id
            FROM webui_notifications
            WHERE user_id = ? AND id != ?
            ORDER BY created_at_ms ASC, id ASC
            LIMIT ?
            """,
            (int(user_id), protected_notification_id, int(to_delete)),
        ),
    )
    ids = [coerce_required_nonempty_str_from_sqlite_row(row, "id") for row in rows]
    _sync_delete_notification_ids(conn, ids)


def sync_create_notification(
    conn: sqlite3.Connection,
    notification_id: str,
    user_id: int,
    type_value: str,
    title: str,
    message: str,
    source: str | None,
    link_json: str | None,
    created_at_ms: int,
    max_per_user: int,
) -> tuple[SQLiteRowDict, bool]:
    if type_value not in NOTIFICATION_TYPE_SQL_VALUES:
        raise StateError("Notification type is invalid.")
    resolved_notification_id = str(notification_id or "").strip()
    if not resolved_notification_id:
        raise StateError("Notification id is invalid.")
    if not is_strict_user_id(user_id):
        raise StateError("Notification user_id is invalid.")
    if (
        (not isinstance(created_at_ms, int))
        or isinstance(created_at_ms, bool)
        or created_at_ms <= 0
    ):
        raise StateError("Notification created_at_ms is invalid.")
    if (not isinstance(max_per_user, int)) or isinstance(max_per_user, bool) or max_per_user <= 0:
        raise StateError("Notification max_per_user is invalid.")
    if source is not None and (not isinstance(source, str) or (not source.strip())):
        raise StateError("Notification source is invalid.")
    _sync_require_valid_notification_text(str(title or ""), label="title")
    _sync_require_valid_notification_text(str(message or ""), label="message")
    if link_json is not None:
        _sync_require_valid_link_json(str(link_json))
    insert_cursor = conn.execute(
        """
        INSERT OR IGNORE INTO webui_notifications (
            id, user_id, type, title, message, source, link_json, created_at_ms, read_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            resolved_notification_id,
            int(user_id),
            str(type_value or ""),
            str(title or ""),
            str(message or ""),
            source,
            link_json,
            int(created_at_ms),
        ),
    )
    inserted = int(insert_cursor.rowcount or 0) > 0
    if inserted:
        _sync_prune_notifications(
            conn,
            user_id=int(user_id),
            max_per_user=int(max_per_user),
            protected_notification_id=resolved_notification_id,
        )
    cursor = conn.execute(
        """
        SELECT id, user_id, type, title, message, source, link_json, created_at_ms, read_at_ms
        FROM webui_notifications
        WHERE id = ? AND user_id = ?
        """,
        (resolved_notification_id, int(user_id)),
    )
    result = sync_fetch_one_as_dict(cursor)
    if result is None:
        raise StateError("Notification not found after INSERT.")
    if inserted:
        sync_enqueue_notification_created_domain_event(
            conn,
            created_at_ms=int(created_at_ms),
            user_id=int(user_id),
            notification_id=resolved_notification_id,
            notification_type=str(type_value or ""),
            title=str(title or ""),
            message=str(message or ""),
            source=source,
            link_json=link_json,
        )
    return (result, inserted)
