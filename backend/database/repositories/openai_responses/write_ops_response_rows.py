"""SoAI - OpenAI Responses response row write operations [backend/database/repositories/openai_responses/write_ops_response_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable
from database.core.storage_fields import require_storage_text
from database.repositories.openai_responses.ownership import (
    normalize_response_owner,
)
from database.repositories.openai_responses.write_ops_shared import (
    normalize_response_mutation_scope,
    read_existing_response_state,
    sync_delete_response_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_delete_response",
    "sync_upsert_response",
)


def sync_upsert_response(
    conn: sqlite3.Connection,
    response_id: str,
    task_id: str,
    user_id: int | None,
    api_key_id: str | None,
    model: str,
    created_at_ms: int,
    status: str,
    store: bool,
    is_background: bool,
    stream_enabled: bool,
    response_json: JSONDict,
) -> None:
    normalized_response_id = require_storage_text(response_id, field="response_id")
    normalized_task_id = require_storage_text(task_id, field="task_id")
    owner = normalize_response_owner(user_id=user_id, api_key_id=api_key_id)
    normalized_model = require_storage_text(model, field="model")
    normalized_status = require_storage_text(status, field="status")
    existing_state = read_existing_response_state(conn, response_id=normalized_response_id)
    if existing_state is not None:
        if existing_state != owner:
            raise ValidationError("Response ownership mismatch.")
    payload_text = serialize_json_compact_stable(response_json)
    conn.execute(
        """
        INSERT INTO openai_responses (
            response_id,
            task_id,
            user_id,
            api_key_id,
            anonymous_owner_id,
            model,
            created_at_ms,
            status,
            store,
            is_background,
            stream_enabled,
            response_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(response_id) DO UPDATE SET
            task_id = excluded.task_id,
            model = excluded.model,
            created_at_ms = excluded.created_at_ms,
            status = excluded.status,
            store = excluded.store,
            is_background = CASE
                WHEN openai_responses.is_background = 1 OR excluded.is_background = 1 THEN 1
                ELSE 0
            END,
            stream_enabled = CASE
                WHEN openai_responses.stream_enabled = 1 OR excluded.stream_enabled = 1 THEN 1
                ELSE 0
            END,
            response_json = excluded.response_json
        WHERE openai_responses.api_key_id IS excluded.api_key_id
          AND openai_responses.user_id IS excluded.user_id
          AND openai_responses.anonymous_owner_id IS excluded.anonymous_owner_id
        """,
        (
            normalized_response_id,
            normalized_task_id,
            owner.user_id,
            owner.api_key_id,
            owner.anonymous_owner_id,
            normalized_model,
            int(created_at_ms),
            normalized_status,
            1 if store else 0,
            1 if is_background else 0,
            1 if stream_enabled else 0,
            payload_text,
        ),
    )


def sync_delete_response(
    conn: sqlite3.Connection,
    response_id: str,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> int:
    scope = normalize_response_mutation_scope(
        response_id,
        user_id=user_id,
        api_key_id=api_key_id,
    )
    return sync_delete_response_row(
        conn,
        scope=scope,
    )
