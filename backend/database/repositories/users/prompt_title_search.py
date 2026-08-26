"""SoAI - Prompt name search repository functions [backend/database/repositories/users/prompt_title_search.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from database.core.query_execution import query_to_dicts
from database.core.row_materialization import sqlite_row_dicts_to_json_dicts
from database.repositories.users.title_search_match import build_user_title_search_match

if TYPE_CHECKING:
    from core.database.protocols import DatabaseCoreProtocol
    from core.types.json import JSONDict

__all__ = ("search_prompt_titles",)


async def search_prompt_titles(
    core: DatabaseCoreProtocol,
    *,
    user_id: int,
    query: str,
    limit: int,
) -> list[JSONDict]:
    match_query = build_user_title_search_match(user_id, query, "name")
    if not match_query or limit <= 0:
        return []

    async def _query(database: aiosqlite.Connection) -> list[JSONDict]:
        rows = await query_to_dicts(
            database,
            """
            SELECT p.id, p.name, p.modified_at_ms, p.color
            FROM webui_prompt_title_search_fts
            JOIN webui_prompts AS p
              ON p.id = webui_prompt_title_search_fts.prompt_id
            WHERE p.user_id = ?
              AND webui_prompt_title_search_fts MATCH ?
            ORDER BY bm25(webui_prompt_title_search_fts), p.modified_at_ms DESC
            LIMIT ?
            """,
            (user_id, match_query, limit),
        )
        return sqlite_row_dicts_to_json_dicts(rows)

    return await core.reader.execute_read(_query)
