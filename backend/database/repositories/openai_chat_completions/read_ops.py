"""SoAI - OpenAI chat completions repository read operations [backend/database/repositories/openai_chat_completions/read_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from database.core.json_codec import safe_json_deserialize_required_object
from database.core.query_execution import query_to_dicts
from database.core.sqlite_numbers import (
    coerce_required_int_from_sqlite_row,
    coerce_required_nonempty_str_from_sqlite_row,
)
from database.core.storage_fields import (
    normalize_optional_api_key_id,
    optional_storage_text,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "read_get_chat_completion_cursor_query",
    "read_get_chat_completion_record_query",
    "read_list_chat_completions_query",
)


async def read_get_chat_completion_record_query(
    database: aiosqlite.Connection,
    *,
    completion_id: str,
    api_key_id: str | None,
) -> JSONDict | None:
    normalized_completion_id = optional_storage_text(completion_id, field="completion_id")
    normalized_api_key_id = normalize_optional_api_key_id(api_key_id)
    if normalized_completion_id is None:
        return None
    rows = await query_to_dicts(
        database,
        """
        SELECT
            completion_id,
            task_id,
            api_key_id,
            model,
            created_at_ms,
            store,
            request_json,
            completion_json,
            metadata_json,
            deleted_at_ms
        FROM openai_chat_completions
        WHERE completion_id = ?
          AND deleted_at_ms IS NULL
          AND store = 1
          AND api_key_id IS ?
        LIMIT 1
        """,
        (normalized_completion_id, normalized_api_key_id),
    )
    if not rows:
        return None
    row = rows[0]
    parsed: JSONDict = dict(row)
    request_decoded = safe_json_deserialize_required_object(
        row.get("request_json"),
        error_message="openai_chat_completions.request_json must be a JSON object.",
    )
    completion_decoded = safe_json_deserialize_required_object(
        row.get("completion_json"),
        error_message="openai_chat_completions.completion_json must be a JSON object.",
    )
    metadata_decoded = safe_json_deserialize_required_object(
        row.get("metadata_json"),
        error_message="openai_chat_completions.metadata_json must be a JSON object.",
    )
    parsed["request_json"] = request_decoded
    parsed["completion_json"] = completion_decoded
    parsed["metadata_json"] = metadata_decoded
    return parsed


async def read_list_chat_completions_query(
    database: aiosqlite.Connection,
    *,
    api_key_id: str | None,
    model: str | None,
    order: str,
    limit: int,
    after_created_at_ms: int | None,
    after_completion_id: str | None,
    metadata_filters: dict[str, str],
) -> tuple[tuple[JSONDict, ...], bool]:
    normalized_api_key_id = normalize_optional_api_key_id(api_key_id)
    normalized_model = optional_storage_text(model, field="model")
    resolved_limit = int(limit)
    if resolved_limit <= 0:
        resolved_limit = 20
    resolved_order = "asc" if str(order or "").strip().lower() == "asc" else "desc"
    sort_dir = "ASC" if resolved_order == "asc" else "DESC"
    op = ">" if resolved_order == "asc" else "<"
    sql_parts: list[str] = ["""
        SELECT completion_id, model, created_at_ms, completion_json, metadata_json
        FROM openai_chat_completions
        WHERE deleted_at_ms IS NULL
          AND store = 1
          AND api_key_id IS ?
          AND (? IS NULL OR model = ?)
        """]
    params: list[str | int | None] = [normalized_api_key_id, normalized_model, normalized_model]
    normalized_after_completion_id = optional_storage_text(
        after_completion_id,
        field="after_completion_id",
    )
    if after_created_at_ms is not None and normalized_after_completion_id is not None:
        sql_parts.append(f"""
          AND (
            created_at_ms {op} ?
            OR (created_at_ms = ? AND completion_id {op} ?)
          )
            """)
        params.extend(
            [int(after_created_at_ms), int(after_created_at_ms), normalized_after_completion_id],
        )
    for meta_key, meta_value in sorted(metadata_filters.items()):
        if not meta_key:
            continue
        sql_parts.append("  AND CAST(json_extract(metadata_json, ?) AS TEXT) = ?")
        params.append(f"$.{meta_key}")
        params.append(str(meta_value))
    sql_parts.append(f"ORDER BY created_at_ms {sort_dir}, completion_id {sort_dir}")
    sql_parts.append("LIMIT ?")
    params.append(int(resolved_limit) + 1)
    rows = await query_to_dicts(database, "\n".join(sql_parts), tuple(params))
    has_more = len(rows) > resolved_limit
    sliced = rows[:resolved_limit]
    results: list[JSONDict] = []
    for row in sliced:
        completion_decoded = safe_json_deserialize_required_object(
            row.get("completion_json"),
            error_message="openai_chat_completions.completion_json must be a JSON object.",
        )
        metadata_decoded = safe_json_deserialize_required_object(
            row.get("metadata_json"),
            error_message="openai_chat_completions.metadata_json must be a JSON object.",
        )
        results.append(
            {
                "completion_id": row.get("completion_id"),
                "model": row.get("model"),
                "created_at_ms": row.get("created_at_ms"),
                "completion_json": completion_decoded,
                "metadata_json": metadata_decoded,
            },
        )
    return (tuple(results), has_more)


async def read_get_chat_completion_cursor_query(
    database: aiosqlite.Connection,
    *,
    completion_id: str,
    api_key_id: str | None,
) -> tuple[int, str] | None:
    normalized_completion_id = optional_storage_text(completion_id, field="completion_id")
    normalized_api_key_id = normalize_optional_api_key_id(api_key_id)
    if normalized_completion_id is None:
        return None
    rows = await query_to_dicts(
        database,
        """
        SELECT created_at_ms, completion_id
        FROM openai_chat_completions
        WHERE completion_id = ?
          AND deleted_at_ms IS NULL
          AND store = 1
          AND api_key_id IS ?
        LIMIT 1
        """,
        (normalized_completion_id, normalized_api_key_id),
    )
    if not rows:
        return None
    row = rows[0]
    return (
        coerce_required_int_from_sqlite_row(row, "created_at_ms"),
        coerce_required_nonempty_str_from_sqlite_row(row, "completion_id"),
    )
