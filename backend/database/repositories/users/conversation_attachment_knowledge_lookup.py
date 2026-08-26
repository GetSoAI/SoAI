"""SoAI - Knowledge attachment lookup helpers [backend/database/repositories/users/conversation_attachment_knowledge_lookup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError, ValidationError
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.conversation_attachment_rows import (
    format_knowledge_attachment_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "fetch_knowledge_attachment_by_client_batch",
    "fetch_knowledge_attachment_by_id",
    "map_knowledge_attachment_integrity_error",
)


def fetch_knowledge_attachment_by_id(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    knowledge_attachment_id: str,
) -> JSONDict | None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT *
            FROM webui_conversation_knowledge_attachments
            WHERE conv_id = ? AND user_id = ? AND id = ?
            """,
            (conv_id, user_id, knowledge_attachment_id),
        ),
    )
    return format_knowledge_attachment_row(row)


def fetch_knowledge_attachment_by_client_batch(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    client_batch_id: str,
) -> JSONDict | None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT *
            FROM webui_conversation_knowledge_attachments
            WHERE conv_id = ? AND user_id = ? AND client_batch_id = ?
            """,
            (conv_id, user_id, client_batch_id),
        ),
    )
    return format_knowledge_attachment_row(row)


def map_knowledge_attachment_integrity_error(exception: sqlite3.IntegrityError) -> Exception:
    constraint_type, detail = parse_sqlite_integrity_error(exception)
    if constraint_type in ("unique", "primary_key"):
        return ConflictError("Knowledge attachment already exists.")
    if constraint_type in ("foreign_key", "check"):
        return ValidationError(
            f"Invalid knowledge attachment data: constraint violation on {detail or 'unknown field'}.",
        )
    return StateError(f"Database constraint violation: {exception}")
