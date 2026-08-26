"""SoAI - OpenAI Responses input item index reads [backend/database/repositories/openai_responses/read_ops_input_item_index.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from database.core.query_execution import query_to_dicts
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row
from database.core.storage_fields import optional_storage_text
from database.repositories.openai_responses.ownership import (
    normalize_response_owner,
)

__all__ = ("read_get_input_item_index_query",)


async def read_get_input_item_index_query(
    database: aiosqlite.Connection,
    *,
    response_id: str,
    item_id: str,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> int | None:
    normalized_response_id = optional_storage_text(response_id, field="response_id")
    normalized_item_id = optional_storage_text(item_id, field="item_id")
    owner = normalize_response_owner(user_id=user_id, api_key_id=api_key_id)
    if normalized_response_id is None or normalized_item_id is None:
        return None
    rows = await query_to_dicts(
        database,
        """
        SELECT i.item_index
        FROM openai_response_input_items AS i
        INNER JOIN openai_responses AS o
            ON o.response_id = i.response_id
        WHERE i.response_id = ?
          AND i.item_id = ?
          AND o.user_id IS ?
          AND o.api_key_id IS ?
          AND o.anonymous_owner_id IS ?
        LIMIT 1
        """,
        (
            normalized_response_id,
            normalized_item_id,
            owner.user_id,
            owner.api_key_id,
            owner.anonymous_owner_id,
        ),
    )
    if not rows:
        return None
    return coerce_required_int_from_sqlite_row(rows[0], "item_index")
