"""SoAI - OpenAI Responses repository read operations [backend/database/repositories/openai_responses/read_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.openai.pagination_coercion import (
    coerce_openai_int,
    coerce_openai_pagination_limit,
)
from database.core.json_codec import safe_json_deserialize_required_object
from database.core.query_execution import query_to_dicts
from database.core.storage_fields import optional_storage_text, require_storage_text
from database.repositories.openai_responses.ownership import (
    normalize_response_owner,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "read_get_response_query",
    "read_get_response_record_query",
    "read_list_events_after_query",
)


async def read_get_response_query(
    database: aiosqlite.Connection,
    *,
    response_id: str,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> JSONDict | None:
    normalized_response_id = optional_storage_text(response_id, field="response_id")
    owner = normalize_response_owner(user_id=user_id, api_key_id=api_key_id)
    if normalized_response_id is None:
        return None
    rows = await query_to_dicts(
        database,
        """
        SELECT o.response_json
        FROM openai_responses AS o
        WHERE o.response_id = ?
          AND o.api_key_id IS ?
          AND o.user_id IS ?
          AND o.anonymous_owner_id IS ?
        LIMIT 1
        """,
        (
            normalized_response_id,
            owner.api_key_id,
            owner.user_id,
            owner.anonymous_owner_id,
        ),
    )
    if not rows:
        return None
    return safe_json_deserialize_required_object(
        rows[0].get("response_json"),
        error_message="openai_responses.response_json must be a JSON object.",
    )


async def read_get_response_record_query(
    database: aiosqlite.Connection,
    *,
    response_id: str,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> JSONDict | None:
    normalized_response_id = optional_storage_text(response_id, field="response_id")
    owner = normalize_response_owner(user_id=user_id, api_key_id=api_key_id)
    if normalized_response_id is None:
        return None
    rows = await query_to_dicts(
        database,
        """
        SELECT o.response_id, o.task_id, o.user_id, o.api_key_id, o.anonymous_owner_id, o.model, o.created_at_ms, o.status, o.store, o.is_background, o.stream_enabled, o.response_json
        FROM openai_responses AS o
        WHERE o.response_id = ?
          AND o.api_key_id IS ?
          AND o.user_id IS ?
          AND o.anonymous_owner_id IS ?
        LIMIT 1
        """,
        (
            normalized_response_id,
            owner.api_key_id,
            owner.user_id,
            owner.anonymous_owner_id,
        ),
    )
    if not rows:
        return None
    row = rows[0]
    parsed: JSONDict = dict(row)
    parsed["response_json"] = safe_json_deserialize_required_object(
        row.get("response_json"),
        error_message="openai_responses.response_json must be a JSON object.",
    )
    return parsed


async def read_list_events_after_query(
    database: aiosqlite.Connection,
    *,
    response_id: str,
    starting_after: int,
    limit: int,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> tuple[tuple[JSONDict, ...], bool]:
    normalized_response_id = require_storage_text(response_id, field="response_id")
    owner = normalize_response_owner(user_id=user_id, api_key_id=api_key_id)
    resolved_starting_after = coerce_openai_int(starting_after, default=-1)
    resolved_limit = coerce_openai_pagination_limit(limit, default=200, maximum=2000)
    rows = await query_to_dicts(
        database,
        """
        SELECT e.event_json
        FROM openai_response_events AS e
        INNER JOIN openai_responses AS o
            ON o.response_id = e.response_id
        WHERE e.response_id = ?
          AND o.api_key_id IS ?
          AND o.user_id IS ?
          AND o.anonymous_owner_id IS ?
          AND e.sequence > ?
        ORDER BY sequence ASC
        LIMIT ?
        """,
        (
            normalized_response_id,
            owner.api_key_id,
            owner.user_id,
            owner.anonymous_owner_id,
            resolved_starting_after,
            int(resolved_limit) + 1,
        ),
    )
    has_more = len(rows) > resolved_limit
    trimmed = rows[:resolved_limit]
    events: list[JSONDict] = []
    for row in trimmed:
        events.append(
            safe_json_deserialize_required_object(
                row.get("event_json"),
                error_message="openai_response_events.event_json must be a JSON object.",
            ),
        )
    return (tuple(events), bool(has_more))
