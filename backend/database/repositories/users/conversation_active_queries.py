"""SoAI - Active conversation read projections [backend/database/repositories/users/conversation_active_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.conversation_query_projection import (
    conversation_query_joins_sql,
    conversation_query_select_sql,
)
from database.repositories.users.conversation_row_formatter import (
    format_conversation_row,
)

if TYPE_CHECKING:
    import aiosqlite

    from core.types.json import JSONDict

__all__ = ("read_active_conversations", "read_conversation")


async def read_conversation(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        f"""
        SELECT c.*, {conversation_query_select_sql()}
        FROM webui_conversations AS c
        {conversation_query_joins_sql()}
        WHERE c.id = ? AND c.user_id = ?
        """,
        (conv_id, user_id),
    )
    return format_conversation_row(row)


async def read_active_conversations(
    database: aiosqlite.Connection,
    *,
    user_id: int,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        f"""
        SELECT c.*, {conversation_query_select_sql()}
        FROM webui_conversations AS c
        {conversation_query_joins_sql()}
        WHERE c.user_id = ? AND c.is_archived = 0
        ORDER BY c.last_modified_at_ms DESC
        """,
        (user_id,),
    )
    return [
        formatted for row in rows if row and (formatted := format_conversation_row(row)) is not None
    ]
