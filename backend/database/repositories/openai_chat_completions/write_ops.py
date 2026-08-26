"""SoAI - OpenAI chat completions repository write operations [backend/database/repositories/openai_chat_completions/write_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ValidationError
from core.types.json import JSONDict
from database.core.json_codec import safe_json_serialize
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.storage_fields import (
    normalize_optional_api_key_id,
    read_stored_optional_api_key_id,
    require_storage_text,
)

__all__ = (
    "sync_mark_chat_completion_deleted",
    "sync_update_chat_completion_metadata",
    "sync_upsert_chat_completion",
)


def _read_existing_chat_completion_api_key_id(
    conn: sqlite3.Connection,
    *,
    completion_id: str,
) -> tuple[bool, str | None]:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT api_key_id
            FROM openai_chat_completions
            WHERE completion_id = ?
            LIMIT 1
            """,
            (completion_id,),
        ),
    )
    if row is None:
        return (False, None)
    if "api_key_id" not in row:
        raise ValidationError("Stored chat completion ownership is invalid.")
    return (
        True,
        read_stored_optional_api_key_id(
            row["api_key_id"],
            error_message="Stored chat completion ownership is invalid.",
        ),
    )


def sync_upsert_chat_completion(
    conn: sqlite3.Connection,
    completion_id: str,
    task_id: str,
    api_key_id: str | None,
    model: str,
    created_at_ms: int,
    store: bool,
    request_json: JSONDict,
    completion_json: JSONDict,
    metadata_json: JSONDict,
) -> None:
    normalized_completion_id = require_storage_text(completion_id, field="completion_id")
    normalized_task_id = require_storage_text(task_id, field="task_id")
    normalized_api_key_id = normalize_optional_api_key_id(api_key_id)
    normalized_model = require_storage_text(model, field="model")
    exists, existing_api_key_id = _read_existing_chat_completion_api_key_id(
        conn,
        completion_id=normalized_completion_id,
    )
    if exists and existing_api_key_id != normalized_api_key_id:
        raise ValidationError("Chat completion ownership mismatch.")
    request_payload = safe_json_serialize(request_json, "request_json", completion_id)
    completion_payload = safe_json_serialize(completion_json, "completion_json", completion_id)
    metadata_payload = safe_json_serialize(metadata_json, "metadata_json", completion_id)
    if request_payload is None or completion_payload is None or metadata_payload is None:
        raise ValidationError("Chat completion JSON payloads cannot be null.")
    conn.execute(
        """
        INSERT INTO openai_chat_completions (
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
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        ON CONFLICT(completion_id) DO UPDATE SET
            task_id = excluded.task_id,
            api_key_id = excluded.api_key_id,
            model = excluded.model,
            created_at_ms = excluded.created_at_ms,
            store = excluded.store,
            request_json = excluded.request_json,
            completion_json = excluded.completion_json,
            metadata_json = excluded.metadata_json,
            deleted_at_ms = NULL
        """,
        (
            normalized_completion_id,
            normalized_task_id,
            normalized_api_key_id,
            normalized_model,
            int(created_at_ms),
            1 if store else 0,
            request_payload,
            completion_payload,
            metadata_payload,
        ),
    )


def sync_mark_chat_completion_deleted(
    conn: sqlite3.Connection,
    completion_id: str,
    deleted_at_ms: int,
    api_key_id: str | None,
) -> int:
    normalized_completion_id = require_storage_text(completion_id, field="completion_id")
    normalized_api_key_id = normalize_optional_api_key_id(api_key_id)
    cursor = conn.execute(
        """
        UPDATE openai_chat_completions
        SET deleted_at_ms = ?
        WHERE completion_id = ?
          AND deleted_at_ms IS NULL
          AND store = 1
          AND api_key_id IS ?
        """,
        (int(deleted_at_ms), normalized_completion_id, normalized_api_key_id),
    )
    return int(cursor.rowcount)


def sync_update_chat_completion_metadata(
    conn: sqlite3.Connection,
    completion_id: str,
    api_key_id: str | None,
    metadata_json: JSONDict,
) -> int:
    normalized_completion_id = require_storage_text(completion_id, field="completion_id")
    normalized_api_key_id = normalize_optional_api_key_id(api_key_id)
    payload = safe_json_serialize(metadata_json, "metadata_json", completion_id)
    if payload is None:
        raise ValidationError("Chat completion metadata_json cannot be null.")
    cursor = conn.execute(
        """
        UPDATE openai_chat_completions
        SET metadata_json = ?
        WHERE completion_id = ?
          AND deleted_at_ms IS NULL
          AND store = 1
          AND api_key_id IS ?
        """,
        (payload, normalized_completion_id, normalized_api_key_id),
    )
    return int(cursor.rowcount)
