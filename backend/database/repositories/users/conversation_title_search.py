"""SoAI - Conversation title search repository functions [backend/database/repositories/users/conversation_title_search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from database.core.query_execution import query_to_dicts
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
    from core.database.protocols import DatabaseCoreProtocol
    from core.types.json import JSONDict

__all__ = ("search_conversation_titles",)


async def search_conversation_titles(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
    query: str,
    limit: int,
) -> list[JSONDict]:
    match_query = build_user_title_search_match(user_id, query, "title")
    if not match_query or limit <= 0:
        return []

    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            f"""
            SELECT c.*, {conversation_query_select_sql()}
            FROM webui_conversation_title_search_fts
            JOIN webui_conversations AS c
              ON c.id = webui_conversation_title_search_fts.conversation_id
            {conversation_query_joins_sql()}
            WHERE c.user_id = ?
              AND c.is_archived = 0
              AND webui_conversation_title_search_fts MATCH ?
            ORDER BY bm25(webui_conversation_title_search_fts), c.last_modified_at_ms DESC
            LIMIT ?
            """,
            (user_id, match_query, limit),
        )
        results: list[JSONDict] = []
        for row in rows:
            formatted = format_conversation_row(row)
            if formatted is not None:
                results.append(attach_conversation_settings_authority(formatted))
        return results

    return await core.reader.execute_read(_query)
