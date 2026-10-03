"""SoAI - Active conversation read projections [backend/database/repositories/users/conversation_active_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.validation.requirements import require_non_negative_exact_int, require_positive_exact_int
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
    from database.core.sqlite_values import SQLiteValue

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
    limit: int | None = None,
    before_created_at_ms: int | None = None,
    before_id: str | None = None,
) -> list[JSONDict]:
    if (before_created_at_ms is None) != (before_id is None):
        raise ValidationError("Conversation cursor requires both creation time and id.")
    if limit is None and before_id is not None:
        raise ValidationError("Conversation cursor requires a page limit.")
    conditions = "c.user_id = ? AND c.is_archived = 0"
    parameters: list[SQLiteValue] = [user_id]
    if before_created_at_ms is not None and before_id is not None:
        require_non_negative_exact_int(
            before_created_at_ms,
            type_message="Conversation cursor creation time must be an integer.",
            range_message="Conversation cursor creation time must be non-negative.",
        )
        conditions += " AND (c.created_at_ms < ? OR (c.created_at_ms = ? AND c.id < ?))"
        parameters.extend((before_created_at_ms, before_created_at_ms, before_id))
    ordering = "c.last_modified_at_ms DESC" if limit is None else "c.created_at_ms DESC, c.id DESC"
    limit_clause = "" if limit is None else "LIMIT ?"
    if limit is not None:
        require_positive_exact_int(
            limit,
            type_message="Conversation page limit must be an integer.",
            range_message="Conversation page limit must be positive.",
        )
        parameters.append(limit)
    rows = await query_to_dicts(
        database,
        f"""
        SELECT c.*, {conversation_query_select_sql()}
        FROM webui_conversations AS c
        {conversation_query_joins_sql()}
        WHERE {conditions}
        ORDER BY {ordering}
        {limit_clause}
        """,
        tuple(parameters),
    )
    return [
        formatted for row in rows if row and (formatted := format_conversation_row(row)) is not None
    ]
