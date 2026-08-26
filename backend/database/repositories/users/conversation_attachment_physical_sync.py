"""SoAI - Physical conversation attachment transactions [backend/database/repositories/users/conversation_attachment_physical_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING

from core.attachments.attachment_constants import WEBUI_CHAT_ATTACHMENT_PURPOSE
from core.errors.exceptions import ConflictError, StateError, ValidationError
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.files.catalog import sync_add_file
from database.repositories.users.conversation_attachment_file_lookup import (
    fetch_file_attachment_by_id,
)
from database.repositories.users.conversation_attachment_rows import (
    format_attachment_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_stage_conversation_attachment",
    "sync_update_attachment_parse_state",
)


def _new_attachment_id() -> str:
    return f"att_{uuid.uuid4().hex}"


def _fetch_attachment_by_client_id(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    client_attachment_id: str,
) -> JSONDict | None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT *
            FROM webui_conversation_attachments
            WHERE conv_id = ? AND user_id = ? AND client_attachment_id = ?
            """,
            (conv_id, user_id, client_attachment_id),
        ),
    )
    return format_attachment_row(row)


def _ensure_existing_stage_matches(
    existing: JSONDict,
    *,
    existing_content_sha256: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
    content_sha256: str,
    preview_type: str,
) -> None:
    if (
        existing.get("filename") == filename
        and existing.get("mime_type") == mime_type
        and existing.get("size_bytes") == size_bytes
        and existing.get("preview_type") == preview_type
        and existing_content_sha256 == content_sha256
    ):
        return
    raise ConflictError("Attachment upload idempotency conflict.")


def _fetch_file_content_sha256(
    conn: sqlite3.Connection,
    *,
    file_id: str,
    user_id: int,
) -> str:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT content_sha256
            FROM files_catalog
            WHERE id = ? AND user_id IS ? AND api_key_id IS NULL
            """,
            (file_id, user_id),
        ),
    )
    content_sha256 = None if row is None else row.get("content_sha256")
    if not isinstance(content_sha256, str):
        raise ConflictError("Attachment upload idempotency catalog row is invalid.")
    try:
        return require_canonical_sha256_hexdigest(
            content_sha256,
            label="Attachment upload idempotency content_sha256",
        )
    except StateError as exception:
        raise ConflictError("Attachment upload idempotency catalog row is invalid.") from exception


def _map_integrity_error(exception: sqlite3.IntegrityError) -> Exception:
    constraint_type, detail = parse_sqlite_integrity_error(exception)
    if constraint_type in ("unique", "primary_key"):
        return ConflictError("Attachment already exists.")
    if constraint_type in ("foreign_key", "check"):
        return ValidationError(
            f"Invalid attachment data: constraint violation on {detail or 'unknown field'}.",
        )
    return StateError(f"Database constraint violation: {exception}")


def sync_stage_conversation_attachment(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    file_id: str,
    file_path: str,
    filename: str,
    mime_type: str,
    size_bytes: int,
    content_sha256: str,
    preview_type: str,
    client_attachment_id: str,
    created_at_ms: int,
    expires_at_ms: int,
) -> JSONDict:
    existing = _fetch_attachment_by_client_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        client_attachment_id=client_attachment_id,
    )
    if existing is not None:
        _ensure_existing_stage_matches(
            existing,
            existing_content_sha256=_fetch_file_content_sha256(
                conn,
                file_id=str(existing.get("file_id") or ""),
                user_id=user_id,
            ),
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            content_sha256=content_sha256,
            preview_type=preview_type,
        )
        return existing
    attachment_id = _new_attachment_id()
    try:
        sync_add_file(
            conn,
            file_id,
            filename,
            WEBUI_CHAT_ATTACHMENT_PURPOSE,
            size_bytes,
            content_sha256,
            created_at_ms,
            file_path,
            user_id,
            None,
            "uploaded",
            None,
        )
        conn.execute(
            """
            INSERT INTO webui_conversation_attachments (
                id, conv_id, user_id, file_id, client_attachment_id, filename, mime_type,
                size_bytes, preview_type, provider_mode, provider_text, provider_text_truncated,
                parse_state, parse_error, parsed_at_ms, state, conversation_input_id,
                message_created_at_ms, attachment_revision, created_at_ms, updated_at_ms,
                expires_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, 'pending', NULL, NULL,
                'staged', NULL, NULL, 0, ?, ?, ?)
            """,
            (
                attachment_id,
                conv_id,
                user_id,
                file_id,
                client_attachment_id,
                filename,
                mime_type,
                size_bytes,
                preview_type,
                created_at_ms,
                created_at_ms,
                expires_at_ms,
            ),
        )
    except sqlite3.IntegrityError as exception:
        raise _map_integrity_error(exception) from exception
    inserted = fetch_file_attachment_by_id(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        attachment_id=attachment_id,
    )
    if inserted is None:
        raise StateError("Attachment row missing after insert.")
    return inserted


def sync_update_attachment_parse_state(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    attachment_id: str,
    provider_mode: str | None,
    provider_text: str | None,
    provider_text_truncated: bool | None,
    parse_state: str,
    parse_error: str | None,
    parsed_at_ms: int | None,
    updated_at_ms: int,
) -> JSONDict | None:
    provider_text_truncated_value = (
        None if provider_text_truncated is None else 1 if provider_text_truncated else 0
    )
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            UPDATE webui_conversation_attachments
            SET provider_mode = ?,
                provider_text = ?,
                provider_text_truncated = ?,
                parse_state = ?,
                parse_error = ?,
                parsed_at_ms = ?,
                updated_at_ms = ?,
                attachment_revision = attachment_revision + 1
            WHERE conv_id = ?
              AND user_id = ?
              AND id = ?
              AND state = 'staged'
              AND parse_state = 'pending'
            RETURNING *
            """,
            (
                provider_mode,
                provider_text,
                provider_text_truncated_value,
                parse_state,
                parse_error,
                parsed_at_ms,
                updated_at_ms,
                conv_id,
                user_id,
                attachment_id,
            ),
        ),
    )
    return format_attachment_row(row)
