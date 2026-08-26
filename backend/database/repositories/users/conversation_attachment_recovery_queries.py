"""SoAI - Conversation attachment startup recovery queries [backend/database/repositories/users/conversation_attachment_recovery_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError
from database.core.query_execution import query_to_dicts
from database.repositories.users.conversation_attachment_draft_reference_sql import (
    attachment_not_referenced_by_draft_sql,
)
from database.repositories.users.conversation_attachment_rows import (
    format_attachment_row,
    format_knowledge_attachment_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRow

__all__ = (
    "list_pending_parse_attachments_query",
    "list_reclaimable_knowledge_attachments_query",
    "list_unbound_attachment_cleanup_query",
)


def _format_attachment_with_path(row: SQLiteRow) -> JSONDict:
    attachment = format_attachment_row(row)
    if attachment is None:
        raise StateError("Attachment recovery row is invalid.")
    file_path = row.get("file_path")
    if isinstance(file_path, str) and file_path:
        attachment["file_path"] = file_path
    content_sha256 = row.get("catalog_content_sha256")
    if isinstance(content_sha256, str) and content_sha256:
        attachment["catalog_content_sha256"] = content_sha256
    catalog_size_bytes = row.get("catalog_size_bytes")
    if isinstance(catalog_size_bytes, int):
        attachment["catalog_size_bytes"] = catalog_size_bytes
    return attachment


async def list_unbound_attachment_cleanup_query(
    conn: aiosqlite.Connection,
    now_ms: int,
    *,
    limit: int,
    cursor_expires_at_ms: int | None,
    cursor_attachment_id: str | None,
) -> list[JSONDict]:
    cursor_filter = ""
    params: list[int | str] = [now_ms]
    if cursor_expires_at_ms is not None and cursor_attachment_id is not None:
        cursor_filter = "AND (a.expires_at_ms > ? OR (a.expires_at_ms = ? AND a.id > ?))"
        params.extend((cursor_expires_at_ms, cursor_expires_at_ms, cursor_attachment_id))
    params.append(limit)
    rows = await query_to_dicts(
        conn,
        f"""
        SELECT a.*, f.file_path, f.content_sha256 AS catalog_content_sha256,
               f.size_bytes AS catalog_size_bytes
        FROM webui_conversation_attachments a
        JOIN files_catalog f
          ON f.id = a.file_id AND f.user_id IS a.user_id AND f.api_key_id IS NULL
        LEFT JOIN webui_conversation_inputs p
          ON p.input_id = a.conversation_input_id
         AND p.conv_id = a.conv_id
         AND p.user_id = a.user_id
        WHERE (
            a.state = 'unused'
            OR (
                a.state IN ('staged', 'queued')
                AND a.expires_at_ms <= ?
                AND (a.conversation_input_id IS NULL OR p.state != 'pending')
                {attachment_not_referenced_by_draft_sql("a")}
            )
        )
          {cursor_filter}
        ORDER BY a.expires_at_ms ASC, a.id ASC
        LIMIT ?
        """,
        tuple(params),
    )
    return [_format_attachment_with_path(row) for row in rows]


async def list_pending_parse_attachments_query(
    conn: aiosqlite.Connection,
    *,
    limit: int,
    cursor_created_at_ms: int | None,
    cursor_attachment_id: str | None,
) -> list[JSONDict]:
    cursor_filter = ""
    params: list[int | str] = []
    if cursor_created_at_ms is not None and cursor_attachment_id is not None:
        cursor_filter = "AND (a.created_at_ms > ? OR (a.created_at_ms = ? AND a.id > ?))"
        params.extend((cursor_created_at_ms, cursor_created_at_ms, cursor_attachment_id))
    params.append(limit)
    rows = await query_to_dicts(
        conn,
        f"""
        SELECT a.*, f.file_path, f.content_sha256 AS catalog_content_sha256,
               f.size_bytes AS catalog_size_bytes
        FROM webui_conversation_attachments a
        JOIN files_catalog f
          ON f.id = a.file_id AND f.user_id IS a.user_id AND f.api_key_id IS NULL
        WHERE a.state = 'staged'
          AND a.parse_state = 'pending'
          {cursor_filter}
        ORDER BY a.created_at_ms ASC, a.id ASC
        LIMIT ?
        """,
        tuple(params),
    )
    return [_format_attachment_with_path(row) for row in rows]


async def list_reclaimable_knowledge_attachments_query(
    conn: aiosqlite.Connection,
    now_ms: int,
    *,
    limit: int,
    cursor_expires_at_ms: int | None,
    cursor_knowledge_attachment_id: str | None,
) -> list[JSONDict]:
    cursor_filter = ""
    params: list[int | str] = [now_ms, now_ms]
    if cursor_expires_at_ms is not None and cursor_knowledge_attachment_id is not None:
        cursor_filter = "AND (k.expires_at_ms > ? OR (k.expires_at_ms = ? AND k.id > ?))"
        params.extend(
            (
                cursor_expires_at_ms,
                cursor_expires_at_ms,
                cursor_knowledge_attachment_id,
            ),
        )
    params.append(limit)
    rows = await query_to_dicts(
        conn,
        f"""
        SELECT k.*
        FROM webui_conversation_knowledge_attachments k
        LEFT JOIN webui_conversation_inputs p
          ON p.input_id = k.conversation_input_id
         AND p.conv_id = k.conv_id
         AND p.user_id = k.user_id
        WHERE (
            (
                k.state IN ('draft', 'queued')
                AND k.expires_at_ms <= ?
                AND (k.conversation_input_id IS NULL OR p.state != 'pending')
            )
            OR (k.state = 'unused' AND k.expires_at_ms <= ?)
        )
          {cursor_filter}
        ORDER BY k.expires_at_ms ASC, k.id ASC
        LIMIT ?
        """,
        tuple(params),
    )
    summaries: list[JSONDict] = []
    for row in rows:
        summary = format_knowledge_attachment_row(row)
        if summary is None:
            raise StateError("Knowledge attachment recovery row is invalid.")
        summaries.append(summary)
    return summaries
