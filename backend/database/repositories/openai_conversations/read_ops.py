"""SoAI - OpenAI conversations read operations [backend/database/repositories/openai_conversations/read_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from database.core.json_codec import safe_json_deserialize_required_object
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.core.sqlite_numbers import (
    coerce_required_int_from_sqlite_row,
    coerce_required_nonempty_str_from_sqlite_row,
)
from database.core.storage_fields import (
    normalize_optional_api_key_id,
    normalize_optional_user_id,
    optional_storage_text,
    require_storage_text,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "read_get_conversation_query",
    "read_get_item_cursor_query",
    "read_list_items_query",
)


async def read_get_conversation_query(
    database: aiosqlite.Connection,
    *,
    conversation_id: str,
    user_id: int | None,
    api_key_id: str | None,
) -> JSONDict | None:
    normalized_id = require_storage_text(conversation_id, field="conversation_id")
    normalized_user_id = normalize_optional_user_id(user_id)
    normalized_api_key_id = normalize_optional_api_key_id(api_key_id)
    row = await query_one_to_dict(
        database,
        """
        SELECT conversation_id, created_at_ms, metadata_json, deleted_at_ms
        FROM openai_conversations
        WHERE deleted_at_ms IS NULL
          AND conversation_id = ?
          AND (? IS NULL OR user_id = ?)
          AND api_key_id IS ?
        """,
        (normalized_id, normalized_user_id, normalized_user_id, normalized_api_key_id),
    )
    if row is None:
        return None
    metadata = safe_json_deserialize_required_object(
        row.get("metadata_json"),
        error_message="openai_conversations.metadata_json must be a JSON object.",
    )
    return {
        "id": coerce_required_nonempty_str_from_sqlite_row(row, "conversation_id"),
        "object": "conversation",
        "created_at_ms": coerce_required_int_from_sqlite_row(row, "created_at_ms"),
        "metadata": metadata,
    }


async def read_get_item_cursor_query(
    database: aiosqlite.Connection,
    *,
    item_id: str,
    conversation_id: str,
    user_id: int | None,
    api_key_id: str | None,
) -> tuple[int, str] | None:
    normalized_item_id = optional_storage_text(item_id, field="item_id")
    normalized_conversation_id = optional_storage_text(
        conversation_id,
        field="conversation_id",
    )
    if normalized_item_id is None or normalized_conversation_id is None:
        return None
    normalized_user_id = normalize_optional_user_id(user_id)
    normalized_api_key_id = normalize_optional_api_key_id(api_key_id)
    row = await query_one_to_dict(
        database,
        """
        SELECT i.created_at_ms, i.item_id
        FROM openai_conversation_items AS i
        INNER JOIN openai_conversations AS c
            ON c.conversation_id = i.conversation_id
        WHERE c.deleted_at_ms IS NULL
          AND i.deleted_at_ms IS NULL
          AND i.conversation_id = ?
          AND i.item_id = ?
          AND (? IS NULL OR i.user_id = ?)
          AND i.api_key_id IS ?
        """,
        (
            normalized_conversation_id,
            normalized_item_id,
            normalized_user_id,
            normalized_user_id,
            normalized_api_key_id,
        ),
    )
    if row is None:
        return None
    return (
        coerce_required_int_from_sqlite_row(row, "created_at_ms"),
        coerce_required_nonempty_str_from_sqlite_row(row, "item_id"),
    )


async def read_list_items_query(
    database: aiosqlite.Connection,
    *,
    conversation_id: str,
    user_id: int | None,
    api_key_id: str | None,
    limit: int,
    order: str,
    after: str | None,
    before: str | None,
) -> tuple[tuple[JSONDict, ...], bool]:
    normalized_conversation_id = require_storage_text(conversation_id, field="conversation_id")
    normalized_user_id = normalize_optional_user_id(user_id)
    normalized_api_key_id = normalize_optional_api_key_id(api_key_id)
    resolved_limit = int(limit)
    if resolved_limit <= 0:
        resolved_limit = 20
    resolved_limit = min(resolved_limit, 100)
    resolved_order = (order or "").strip().lower()
    if resolved_order not in {"asc", "desc"}:
        resolved_order = "desc"
    where_clauses: list[str] = [
        "c.deleted_at_ms IS NULL",
        "i.deleted_at_ms IS NULL",
        "i.conversation_id = ?",
        "(? IS NULL OR i.user_id = ?)",
        "i.api_key_id IS ?",
    ]
    params: list[SQLiteValue] = [normalized_conversation_id, normalized_user_id, normalized_user_id]
    params.append(normalized_api_key_id)
    normalized_after = optional_storage_text(after, field="after")
    if normalized_after is not None:
        cursor = await read_get_item_cursor_query(
            database,
            item_id=normalized_after,
            conversation_id=normalized_conversation_id,
            user_id=normalized_user_id,
            api_key_id=normalized_api_key_id,
        )
        if cursor is None:
            return ((), False)
        after_created_at, after_id = cursor
        comparator = ">" if resolved_order == "asc" else "<"
        where_clauses.append(f"(i.created_at_ms, i.item_id) {comparator} (?, ?)")
        params.extend([int(after_created_at), str(after_id)])
    normalized_before = optional_storage_text(before, field="before")
    if normalized_before is not None:
        cursor = await read_get_item_cursor_query(
            database,
            item_id=normalized_before,
            conversation_id=normalized_conversation_id,
            user_id=normalized_user_id,
            api_key_id=normalized_api_key_id,
        )
        if cursor is None:
            return ((), False)
        before_created_at, before_id = cursor
        comparator = "<" if resolved_order == "asc" else ">"
        where_clauses.append(f"(i.created_at_ms, i.item_id) {comparator} (?, ?)")
        params.extend([int(before_created_at), str(before_id)])
    where_sql = " AND ".join(where_clauses)
    sql = f"""
        SELECT i.item_id, i.item_json, i.created_at_ms
        FROM openai_conversation_items AS i
        INNER JOIN openai_conversations AS c
            ON c.conversation_id = i.conversation_id
        WHERE {where_sql}
        ORDER BY i.created_at_ms {resolved_order.upper()}, i.item_id {resolved_order.upper()}
        LIMIT ?
    """
    params.append(int(resolved_limit) + 1)
    rows = await query_to_dicts(database, sql, tuple(params))
    has_more = len(rows) > resolved_limit
    trimmed = rows[:resolved_limit]
    items: list[JSONDict] = []
    for row in trimmed:
        items.append(
            safe_json_deserialize_required_object(
                row.get("item_json"),
                error_message="openai_conversation_items.item_json must be a JSON object.",
            ),
        )
    return (tuple(items), bool(has_more))
