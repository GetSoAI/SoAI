"""SoAI - Notification update/delete sync database operations [backend/database/repositories/users/notifications_sync_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError, ValidationError
from core.notifications.notification_source_visibility import (
    normalize_notification_excluded_sources,
)
from core.timing.epoch import epoch_ms
from core.users.user_id import is_strict_user_id
from database.core.query_execution import (
    sync_fetch_all_as_dicts,
    sync_fetch_one_as_dict,
)
from database.core.sqlite_numbers import coerce_required_nonempty_str_from_sqlite_row
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.notifications_event_outbox import (
    sync_enqueue_notification_deleted_domain_event,
    sync_enqueue_notifications_cleared_domain_event,
    sync_enqueue_notifications_marked_read_domain_event,
)

__all__ = (
    "sync_clear_notifications",
    "sync_delete_notification",
    "sync_mark_notifications_read",
    "sync_open_notification",
)


def sync_mark_notifications_read(
    conn: sqlite3.Connection,
    user_id: int,
    notification_ids: list[str],
) -> int:
    if not is_strict_user_id(user_id):
        raise StateError("Notification updates require user_id to be a positive integer.")
    normalized_notification_ids: list[str] = []
    for notification_id in notification_ids:
        if not isinstance(notification_id, str):
            raise StateError("notification_ids must contain strings.")
        normalized_notification_id = notification_id.strip()
        if not normalized_notification_id:
            raise StateError("notification_ids must contain non-empty strings.")
        if normalized_notification_id not in normalized_notification_ids:
            normalized_notification_ids.append(normalized_notification_id)
    if not normalized_notification_ids:
        return 0
    placeholders = ", ".join("?" for _ in normalized_notification_ids)
    now_ms = epoch_ms()
    rows = sync_fetch_all_as_dicts(
        conn.execute(
            f"""
            UPDATE webui_notifications
            SET read_at_ms = ?
            WHERE user_id = ? AND read_at_ms IS NULL AND id IN ({placeholders})
            RETURNING id
            """,
            (now_ms, int(user_id), *normalized_notification_ids),
        ),
    )
    changed_notification_ids: list[str] = []
    for row in rows:
        try:
            changed_notification_ids.append(coerce_required_nonempty_str_from_sqlite_row(row, "id"))
        except ValidationError as exception:
            raise StateError(
                "Notification updates query returned an invalid notification id.",
            ) from exception
    if not changed_notification_ids:
        return 0
    changed_notification_id_set = set(changed_notification_ids)
    changed_notification_ids = [
        notification_id
        for notification_id in normalized_notification_ids
        if notification_id in changed_notification_id_set
    ]
    updated_count = len(changed_notification_ids)
    if updated_count > 0:
        sync_enqueue_notifications_marked_read_domain_event(
            conn,
            created_at_ms=now_ms,
            user_id=int(user_id),
            notification_ids=changed_notification_ids,
        )
    return updated_count


def sync_open_notification(
    conn: sqlite3.Connection,
    user_id: int,
    notification_id: str,
    excluded_sources: frozenset[str],
) -> SQLiteRowDict | None:
    if not is_strict_user_id(user_id):
        raise StateError("Notification updates require user_id to be a positive integer.")
    if not isinstance(notification_id, str) or not notification_id.strip():
        raise StateError("Notification open requires a non-empty notification_id.")
    normalized_notification_id = notification_id.strip()
    normalized_excluded_sources = normalize_notification_excluded_sources(excluded_sources)
    source_filter = ""
    source_filter_params: list[str] = []
    if normalized_excluded_sources:
        placeholders = ", ".join("?" for _ in normalized_excluded_sources)
        source_filter = f" AND (source IS NULL OR source NOT IN ({placeholders}))"
        source_filter_params.extend(normalized_excluded_sources)
    existing = sync_fetch_one_as_dict(
        conn.execute(
            f"""
            SELECT id, user_id, type, title, message, source, link_json, created_at_ms, read_at_ms
            FROM webui_notifications
            WHERE user_id = ? AND id = ?{source_filter}
            LIMIT 1
            """,
            (int(user_id), normalized_notification_id, *source_filter_params),
        ),
    )
    if existing is None:
        return None
    now_ms = epoch_ms()
    changed = conn.execute(
        """
        UPDATE webui_notifications
        SET read_at_ms = ?
        WHERE user_id = ? AND id = ? AND read_at_ms IS NULL
        """,
        (now_ms, int(user_id), normalized_notification_id),
    ).rowcount
    result = sync_fetch_one_as_dict(
        conn.execute(
            f"""
            SELECT id, user_id, type, title, message, source, link_json, created_at_ms, read_at_ms
            FROM webui_notifications
            WHERE user_id = ? AND id = ?{source_filter}
            LIMIT 1
            """,
            (int(user_id), normalized_notification_id, *source_filter_params),
        ),
    )
    if result is not None and int(changed or 0) > 0:
        sync_enqueue_notifications_marked_read_domain_event(
            conn,
            created_at_ms=now_ms,
            user_id=int(user_id),
            notification_ids=[normalized_notification_id],
        )
    return result


def sync_delete_notification(
    conn: sqlite3.Connection,
    user_id: int,
    notification_id: str,
) -> bool:
    if not is_strict_user_id(user_id):
        raise StateError("Notification updates require user_id to be a positive integer.")
    if not isinstance(notification_id, str) or not notification_id.strip():
        raise StateError("Notification delete requires a non-empty notification_id.")
    normalized_notification_id = notification_id.strip()
    now_ms = epoch_ms()
    deleted = conn.execute(
        "DELETE FROM webui_notifications WHERE user_id = ? AND id = ?",
        (int(user_id), normalized_notification_id),
    ).rowcount
    if int(deleted or 0) <= 0:
        return False
    sync_enqueue_notification_deleted_domain_event(
        conn,
        created_at_ms=now_ms,
        user_id=int(user_id),
        notification_id=normalized_notification_id,
    )
    return True


def sync_clear_notifications(
    conn: sqlite3.Connection,
    user_id: int,
) -> int:
    if not is_strict_user_id(user_id):
        raise StateError("Notification updates require user_id to be a positive integer.")
    now_ms = epoch_ms()
    deleted = conn.execute(
        "DELETE FROM webui_notifications WHERE user_id = ?",
        (int(user_id),),
    ).rowcount
    deleted_count = int(deleted or 0)
    if deleted_count > 0:
        sync_enqueue_notifications_cleared_domain_event(
            conn,
            created_at_ms=now_ms,
            user_id=int(user_id),
        )
    return deleted_count
