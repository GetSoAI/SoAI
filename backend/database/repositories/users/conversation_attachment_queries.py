"""SoAI - Conversation attachment read queries [backend/database/repositories/users/conversation_attachment_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.users.conversation_attachment_item_rows import (
    format_knowledge_attachment_item_row,
)
from database.repositories.users.conversation_attachment_rows import (
    format_attachment_row,
    format_knowledge_attachment_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_attachment_by_client_id_query",
    "get_attachment_query",
    "get_knowledge_attachment_items_page_query",
    "get_knowledge_attachment_query",
    "list_draft_knowledge_attachments_query",
)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def get_attachment_query(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
    attachment_id: str,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        """
        SELECT *
        FROM webui_conversation_attachments
        WHERE conv_id = ? AND user_id = ? AND id = ?
        """,
        (conv_id, user_id, attachment_id),
    )
    return format_attachment_row(row)


async def get_attachment_by_client_id_query(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
    client_attachment_id: str,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        """
        SELECT *
        FROM webui_conversation_attachments
        WHERE conv_id = ? AND user_id = ? AND client_attachment_id = ?
        """,
        (conv_id, user_id, client_attachment_id),
    )
    return format_attachment_row(row)


async def list_draft_knowledge_attachments_query(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
    *,
    preview_limit: int,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        """
        SELECT *
        FROM webui_conversation_knowledge_attachments
        WHERE conv_id = ? AND user_id = ? AND state = 'draft' AND expires_at_ms > ?
        ORDER BY created_at_ms ASC, id ASC
        """,
        (conv_id, user_id, epoch_ms()),
    )
    formatted: list[JSONDict] = []
    for row in rows:
        summary = format_knowledge_attachment_row(row)
        if summary is not None:
            preview_rows = await query_to_dicts(
                database,
                """
                SELECT *
                FROM webui_conversation_knowledge_attachment_items
                WHERE conv_id = ? AND user_id = ? AND knowledge_attachment_id = ?
                ORDER BY item_index ASC, id ASC
                LIMIT ?
                """,
                (conv_id, user_id, row["id"], preview_limit),
            )
            summary["preview_items"] = [
                format_knowledge_attachment_item_row(preview_row) for preview_row in preview_rows
            ]
            formatted.append(summary)
    return formatted


async def get_knowledge_attachment_query(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        """
        SELECT *
        FROM webui_conversation_knowledge_attachments
        WHERE conv_id = ? AND user_id = ? AND id = ?
        """,
        (conv_id, user_id, knowledge_attachment_id),
    )
    return format_knowledge_attachment_row(row)


async def get_knowledge_attachment_items_page_query(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
    *,
    limit: int,
    cursor_item_index: int | None,
    cursor_id: int | None,
    status: str | None,
    query: str | None,
) -> JSONDict | None:
    summary = await get_knowledge_attachment_query(
        database,
        conv_id,
        user_id,
        knowledge_attachment_id,
    )
    if summary is None:
        return None
    base_params: list[str | int] = [conv_id, user_id, knowledge_attachment_id]
    base_filters = [
        "conv_id = ?",
        "user_id = ?",
        "knowledge_attachment_id = ?",
    ]
    if status is not None:
        base_filters.append("rag_status = ?")
        base_params.append(status)
    if query is not None:
        base_filters.append("filename LIKE ? ESCAPE '\\'")
        base_params.append(f"%{_escape_like(query)}%")
    count_sql = f"""
        SELECT COUNT(*) AS count
        FROM webui_conversation_knowledge_attachment_items
        WHERE {' AND '.join(base_filters)}
        """
    count_row = await query_one_to_dict(database, count_sql, tuple(base_params))
    count = 0
    if count_row is not None:
        count_value = count_row.get("count")
        if is_strict_int(count_value):
            count = count_value
    params = list(base_params)
    filters = list(base_filters)
    if cursor_item_index is not None and cursor_id is not None:
        filters.append("(item_index > ? OR (item_index = ? AND id > ?))")
        params.extend((cursor_item_index, cursor_item_index, cursor_id))
    sql = f"""
        SELECT *
        FROM webui_conversation_knowledge_attachment_items
        WHERE {' AND '.join(filters)}
        ORDER BY item_index ASC, id ASC
        LIMIT ?
        """
    params.append(limit + 1)
    rows = await query_to_dicts(database, sql, tuple(params))
    formatted = [format_knowledge_attachment_item_row(row) for row in rows[:limit]]
    next_cursor: JSONDict | None = None
    if len(rows) > limit and formatted:
        last = formatted[-1]
        next_cursor = {"item_index": last["item_index"], "id": last["id"]}
    return {
        "items": formatted,
        "count": count,
        "limit": limit,
        "next_cursor": next_cursor,
        "attachment_revision": summary["attachment_revision"],
    }
