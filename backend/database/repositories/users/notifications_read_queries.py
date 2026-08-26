"""SoAI - User notification read queries [backend/database/repositories/users/notifications_read_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.database.protocols import DatabaseReaderProtocol
from core.errors.exceptions import StateError, ValidationError
from core.notifications.notification_record_models import (
    NotificationRecord,
    NotificationsListCursor,
    NotificationsListPage,
)
from core.notifications.notification_source_visibility import (
    normalize_notification_excluded_sources,
)
from database.core.query_execution import query_to_dicts
from database.repositories.users.notifications_row_normalization import (
    normalize_notification_row,
)
from database.repositories.users.notifications_value_validation import (
    coerce_notification_count,
    normalize_notification_cursor_created_at,
    require_notification_list_limit,
    require_notification_user_id,
)

__all__ = (
    "get_notification_counts_query",
    "list_notifications_query",
)


async def list_notifications_query(
    reader: DatabaseReaderProtocol,
    user_id: int,
    *,
    limit: int,
    before_created_at_ms: int | None,
    before_id: str | None,
    unread_only: bool,
    excluded_sources: frozenset[str],
) -> NotificationsListPage:
    resolved_user_id = require_notification_user_id(user_id)
    resolved_limit = require_notification_list_limit(limit)
    resolved_before_created_at_ms = normalize_notification_cursor_created_at(before_created_at_ms)
    resolved_before_id = str(before_id or "").strip() if before_id is not None else None
    if (resolved_before_created_at_ms is None) != (resolved_before_id is None):
        raise ValidationError(
            "Notification cursor requires both before_created_at_ms and before_id.",
        )
    normalized_excluded_sources = normalize_notification_excluded_sources(excluded_sources)

    async def _query(database: aiosqlite.Connection) -> NotificationsListPage:
        query_suffix = ""
        params: list[int | str] = [resolved_user_id]
        if unread_only:
            query_suffix += " AND read_at_ms IS NULL"
        if normalized_excluded_sources:
            placeholders = ", ".join("?" for _ in normalized_excluded_sources)
            query_suffix += f" AND (source IS NULL OR source NOT IN ({placeholders}))"
            params.extend(normalized_excluded_sources)
        if resolved_before_created_at_ms is not None and resolved_before_id is not None:
            query_suffix += " AND (created_at_ms < ? OR (created_at_ms = ? AND id < ?))"
            params.extend(
                [
                    int(resolved_before_created_at_ms),
                    int(resolved_before_created_at_ms),
                    resolved_before_id,
                ],
            )
        params.append(int(resolved_limit) + 1)
        rows = await query_to_dicts(
            database,
            f"""
            SELECT id, user_id, type, title, message, source, link_json,
                created_at_ms, read_at_ms
            FROM webui_notifications
            WHERE user_id = ?{query_suffix}
            ORDER BY created_at_ms DESC, id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        results: list[NotificationRecord] = []
        for row in rows:
            notification = normalize_notification_row(row)
            if notification is None:
                raise StateError("Notification query returned an empty row.")
            results.append(notification)
        has_more = len(results) > resolved_limit
        visible_results = results[:resolved_limit]
        next_cursor: NotificationsListCursor | None = None
        if has_more and visible_results:
            last_visible = visible_results[-1]
            next_cursor = NotificationsListCursor(
                created_at_ms=last_visible.created_at_ms,
                id=last_visible.id,
            )
        return NotificationsListPage(
            notifications=visible_results,
            next_cursor=next_cursor,
        )

    return await reader.execute_read(_query)


async def get_notification_counts_query(
    reader: DatabaseReaderProtocol,
    user_id: int,
    *,
    excluded_sources: frozenset[str],
) -> tuple[int, int]:
    resolved_user_id = require_notification_user_id(user_id)
    normalized_excluded_sources = normalize_notification_excluded_sources(excluded_sources)

    async def _query(database: aiosqlite.Connection) -> tuple[int, int]:
        query_suffix = ""
        params: list[int | str] = [resolved_user_id]
        if normalized_excluded_sources:
            placeholders = ", ".join("?" for _ in normalized_excluded_sources)
            query_suffix = f" AND (source IS NULL OR source NOT IN ({placeholders}))"
            params.extend(normalized_excluded_sources)
        rows = await query_to_dicts(
            database,
            f"""
            SELECT
                COUNT(*) AS total_count,
                COUNT(CASE WHEN read_at_ms IS NULL THEN 1 END) AS unread_count
            FROM webui_notifications
            WHERE user_id = ?{query_suffix}
            """,
            tuple(params),
        )
        if not rows:
            return (0, 0)
        total_count = coerce_notification_count(rows[0].get("total_count"))
        unread_count = coerce_notification_count(rows[0].get("unread_count"))
        return (total_count, unread_count)

    return await reader.execute_read(_query)
