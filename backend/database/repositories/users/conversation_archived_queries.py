"""SoAI - Archived conversation read queries [backend/database/repositories/users/conversation_archived_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.conversations.archived_conversation_models import (
    ArchivedConversationsCursor,
    ArchivedConversationsPage,
    ArchivedConversationSummary,
)
from core.errors.exceptions import StateError, ValidationError
from core.sqlite.aiosqlite_cleanup import wait_for_aiosqlite_cleanup
from database.core.query_execution import query_to_dicts
from database.core.row_fields import (
    require_row_non_negative_int,
)
from database.repositories.users.conversation_query_projection import (
    conversation_query_joins_sql,
    conversation_query_select_sql,
)
from database.repositories.users.conversation_row_formatter import (
    attach_conversation_settings_authority,
    format_conversation_row,
)
from database.repositories.users.title_search_match import build_user_title_search_match

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol, DatabaseReaderProtocol
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "list_archived_conversations_query",
    "search_archived_conversation_titles_query",
)


async def list_archived_conversations_query(
    reader: DatabaseReaderProtocol,
    user_id: int,
    *,
    limit: int,
    before_last_modified_at_ms: int | None,
    before_id: str | None,
) -> ArchivedConversationsPage:
    resolved_before_id = str(before_id or "").strip() if before_id is not None else None
    if (before_last_modified_at_ms is None) != (resolved_before_id is None):
        raise ValidationError(
            "Archived conversation cursor requires both before_last_modified_at_ms and before_id.",
        )

    async def _query(database: aiosqlite.Connection) -> ArchivedConversationsPage:
        committed = False
        await database.execute("BEGIN")
        try:
            total_rows = await query_to_dicts(
                database,
                "SELECT COUNT(*) AS total_count FROM webui_conversations WHERE user_id = ? AND is_archived = 1",
                (user_id,),
            )
            if not total_rows:
                raise StateError("Archived conversation total_count is invalid.")
            total_count = require_row_non_negative_int(
                total_rows[0].get("total_count"),
                label="Archived conversation total_count",
                build_error=StateError,
            )
            cursor_clause = ""
            params: list[int | str] = [user_id]
            if before_last_modified_at_ms is not None and resolved_before_id is not None:
                cursor_clause = (
                    " AND (last_modified_at_ms < ? OR (last_modified_at_ms = ? AND id < ?))"
                )
                params.extend(
                    [before_last_modified_at_ms, before_last_modified_at_ms, resolved_before_id],
                )
            params.append(limit + 1)
            rows = await query_to_dicts(
                database,
                f"""
                SELECT c.*, {conversation_query_select_sql()}
                FROM webui_conversations AS c
                {conversation_query_joins_sql()}
                WHERE c.user_id = ? AND c.is_archived = 1{cursor_clause}
                ORDER BY c.last_modified_at_ms DESC, c.id DESC
                LIMIT ?
                """,
                tuple(params),
            )
            summaries = [build_archived_conversation_summary(row) for row in rows]
            has_more = len(summaries) > limit
            visible_summaries = summaries[:limit]
            next_cursor: ArchivedConversationsCursor | None = None
            if has_more and visible_summaries:
                last_visible = visible_summaries[-1]
                next_cursor = ArchivedConversationsCursor(
                    last_modified_at_ms=last_visible.last_modified_at_ms,
                    id=last_visible.id,
                )
            await database.execute("COMMIT")
            committed = True
            return ArchivedConversationsPage(
                conversations=visible_summaries,
                total_count=total_count,
                next_cursor=next_cursor,
            )
        finally:
            if not committed:
                await wait_for_aiosqlite_cleanup(database.execute("ROLLBACK"))

    return await reader.execute_read(_query)


async def search_archived_conversation_titles_query(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
    query: str,
    limit: int,
) -> list[ArchivedConversationSummary]:
    match_query = build_user_title_search_match(user_id, query, "title")
    if not match_query or limit <= 0:
        return []

    async def _query(database: aiosqlite.Connection) -> list[ArchivedConversationSummary]:
        rows = await query_to_dicts(
            database,
            f"""
            SELECT c.*, {conversation_query_select_sql()}
            FROM webui_conversation_title_search_fts
            JOIN webui_conversations AS c
              ON c.id = webui_conversation_title_search_fts.conversation_id
            {conversation_query_joins_sql()}
            WHERE c.user_id = ?
              AND c.is_archived = 1
              AND webui_conversation_title_search_fts MATCH ?
            ORDER BY bm25(webui_conversation_title_search_fts), c.last_modified_at_ms DESC
            LIMIT ?
            """,
            (user_id, match_query, limit),
        )
        return [build_archived_conversation_summary(row) for row in rows]

    return await core.reader.execute_read(_query)


def build_archived_conversation_summary(row: SQLiteRowDict) -> ArchivedConversationSummary:
    formatted = format_conversation_row(row)
    if formatted is None:
        raise StateError("Archived conversation record is missing.")
    return ArchivedConversationSummary.model_validate(
        attach_conversation_settings_authority(formatted),
    )
