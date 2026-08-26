"""SoAI - Shared OpenAI Responses mutation helpers [backend/database/repositories/openai_responses/write_ops_shared.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import (
    coerce_required_int_from_sqlite_row,
)
from database.core.sqlite_values import SQLiteValue
from database.core.storage_fields import require_storage_text
from database.repositories.openai_responses.ownership import (
    ResponseOwner,
    normalize_response_owner,
    read_stored_response_owner,
)

__all__ = (
    "ResponseMutationScope",
    "normalize_response_mutation_scope",
    "read_existing_response_state",
    "read_next_response_event_sequence",
    "sync_delete_response_row",
    "sync_update_response_row_status",
)

_RESPONSE_OWNER_FILTER_SQL = """
    response_id = ?
      AND api_key_id IS ?
      AND user_id IS ?
      AND anonymous_owner_id IS ?
"""


@dataclass(frozen=True, slots=True)
class ResponseMutationScope:
    response_id: str
    owner: ResponseOwner


def normalize_response_mutation_scope(
    response_id: str,
    *,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> ResponseMutationScope:
    return ResponseMutationScope(
        response_id=require_storage_text(response_id, field="response_id"),
        owner=normalize_response_owner(user_id=user_id, api_key_id=api_key_id),
    )


def read_existing_response_state(
    conn: sqlite3.Connection,
    *,
    response_id: str,
) -> ResponseOwner | None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT user_id, api_key_id, anonymous_owner_id FROM openai_responses WHERE response_id = ? LIMIT 1",
            (response_id,),
        ),
    )
    if row is None:
        return None
    return read_stored_response_owner(row)


def sync_update_response_row_status(
    conn: sqlite3.Connection,
    *,
    scope: ResponseMutationScope,
    status: str,
    response_json_text: str | None,
    allowed_statuses: tuple[str, ...] | None = None,
) -> int:
    normalized_status = require_storage_text(status, field="status")
    params: list[SQLiteValue] = [normalized_status]
    set_clause = "status = ?"
    if response_json_text is not None:
        set_clause = "status = ?, response_json = ?"
        params.append(response_json_text)
    params.extend(
        (
            scope.response_id,
            scope.owner.api_key_id,
            scope.owner.user_id,
            scope.owner.anonymous_owner_id,
        ),
    )
    sql = f"""
        UPDATE openai_responses
        SET {set_clause}
        WHERE {_RESPONSE_OWNER_FILTER_SQL}
    """
    if allowed_statuses is not None:
        placeholders = ", ".join("?" for _status in allowed_statuses)
        sql += f" AND openai_responses.status IN ({placeholders})"
        params.extend(allowed_statuses)
    cursor = conn.execute(sql, tuple(params))
    return int(cursor.rowcount)


def sync_delete_response_row(
    conn: sqlite3.Connection,
    *,
    scope: ResponseMutationScope,
) -> int:
    cursor = conn.execute(
        f"""
        DELETE FROM openai_responses
        WHERE {_RESPONSE_OWNER_FILTER_SQL}
        """,
        (
            scope.response_id,
            scope.owner.api_key_id,
            scope.owner.user_id,
            scope.owner.anonymous_owner_id,
        ),
    )
    return int(cursor.rowcount)


def read_next_response_event_sequence(
    conn: sqlite3.Connection,
    *,
    response_id: str,
) -> int:
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT COALESCE(MAX(sequence), -1) AS max_seq FROM openai_response_events WHERE response_id = ?",
            (response_id,),
        ),
    )
    max_seq = coerce_required_int_from_sqlite_row(row, "max_seq") if row else -1
    return max_seq + 1
