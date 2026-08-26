"""SoAI - OpenAI Responses input item read operations [backend/database/repositories/openai_responses/read_ops_input_items.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.openai.pagination_coercion import coerce_openai_pagination_limit
from database.core.json_codec import safe_json_deserialize_required_object
from database.core.query_execution import query_to_dicts
from database.core.storage_fields import optional_storage_text, require_storage_text
from database.repositories.openai_responses.ownership import (
    normalize_response_owner,
)
from database.repositories.openai_responses.read_ops_input_item_index import (
    read_get_input_item_index_query,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = ("read_list_input_items_query",)


async def read_list_input_items_query(
    database: aiosqlite.Connection,
    *,
    response_id: str,
    limit: int,
    order: str,
    after: str | None,
    before: str | None,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> JSONDict:
    normalized_response_id = require_storage_text(response_id, field="response_id")
    owner = normalize_response_owner(user_id=user_id, api_key_id=api_key_id)
    resolved_limit = coerce_openai_pagination_limit(limit, default=20, maximum=100)
    resolved_order = (order or "").strip().lower()
    if resolved_order not in {"asc", "desc"}:
        resolved_order = "desc"
    where_clauses: list[str] = [
        "o.response_id = ?",
        "o.user_id IS ?",
        "o.api_key_id IS ?",
        "o.anonymous_owner_id IS ?",
    ]
    params: list[SQLiteValue] = [
        normalized_response_id,
        owner.user_id,
        owner.api_key_id,
        owner.anonymous_owner_id,
    ]
    normalized_after = optional_storage_text(after, field="after")
    if normalized_after is not None:
        after_index = await read_get_input_item_index_query(
            database,
            response_id=normalized_response_id,
            item_id=normalized_after,
            user_id=owner.user_id,
            api_key_id=api_key_id,
        )
        if after_index is None:
            return {
                "object": "list",
                "data": [],
                "first_id": None,
                "last_id": None,
                "has_more": False,
            }
        if resolved_order == "asc":
            where_clauses.append("item_index > ?")
        else:
            where_clauses.append("item_index < ?")
        params.append(int(after_index))
    normalized_before = optional_storage_text(before, field="before")
    if normalized_before is not None:
        before_index = await read_get_input_item_index_query(
            database,
            response_id=normalized_response_id,
            item_id=normalized_before,
            user_id=owner.user_id,
            api_key_id=api_key_id,
        )
        if before_index is None:
            return {
                "object": "list",
                "data": [],
                "first_id": None,
                "last_id": None,
                "has_more": False,
            }
        if resolved_order == "asc":
            where_clauses.append("item_index < ?")
        else:
            where_clauses.append("item_index > ?")
        params.append(int(before_index))
    where_sql = " AND ".join(where_clauses)
    sql = f"""
        SELECT item_id, item_json
        FROM openai_response_input_items AS i
        INNER JOIN openai_responses AS o
            ON o.response_id = i.response_id
        WHERE {where_sql}
        ORDER BY i.item_index {resolved_order.upper()}
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
                error_message="openai_response_input_items.item_json must be a JSON object.",
            ),
        )
    first_id = items[0].get("id") if items else None
    last_id = items[-1].get("id") if items else None
    return {
        "object": "list",
        "data": items,
        "first_id": first_id if isinstance(first_id, str) else None,
        "last_id": last_id if isinstance(last_id, str) else None,
        "has_more": bool(has_more),
    }
