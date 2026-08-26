"""SoAI - Mail message body repository writes [backend/database/repositories/users/mail/message_body_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.timing.epoch import epoch_ms
from core.users.account_identifier_validation import (
    optional_mail_attachment_id,
    require_mail_message_id,
)
from core.validation.strings import coerce_optional_trimmed_str
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.account_validation import (
    optional_json_object,
    require_bool_int,
    require_nonnegative_int,
    require_text,
    require_user_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_replace_mail_message_body",)


def sync_replace_mail_message_body(
    conn: sqlite3.Connection,
    /,
    user_id: int,
    message_id: str,
    body_text: str,
    body_html: str | None,
    total_chars: int,
    parts: list[JSONDict],
) -> SQLiteRowDict | None:
    normalized_user_id = require_user_id(user_id)
    normalized_message_id = require_mail_message_id(message_id)
    existing = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT id FROM mail_messages WHERE user_id = ? AND id = ? LIMIT 1",
            (normalized_user_id, normalized_message_id),
        ),
    )
    if existing is None:
        return None
    conn.execute("DELETE FROM mail_message_bodies WHERE message_id = ?", (normalized_message_id,))
    conn.execute("DELETE FROM mail_message_parts WHERE message_id = ?", (normalized_message_id,))
    conn.execute(
        """
        INSERT INTO mail_message_bodies (message_id, body_text, body_html, total_chars, cached_at_ms)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            normalized_message_id,
            require_text(body_text, "body_text"),
            coerce_optional_trimmed_str(body_html),
            require_nonnegative_int(total_chars, "total_chars"),
            epoch_ms(),
        ),
    )
    for part in parts:
        conn.execute(
            """
            INSERT INTO mail_message_parts (
                message_id, part_id, attachment_id, mime_type, filename, is_inline,
                size_bytes, attachment_remote_spec_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_message_id,
                require_text(part.get("part_id"), "part_id"),
                optional_mail_attachment_id(part.get("attachment_id")),
                require_text(part.get("mime_type"), "mime_type"),
                coerce_optional_trimmed_str(part.get("filename")),
                require_bool_int(part.get("is_inline"), "is_inline"),
                require_nonnegative_int(part.get("size_bytes"), "size_bytes"),
                optional_json_object(part.get("attachment_remote_spec")),
            ),
        )
    return sync_fetch_one_as_dict(
        conn.execute(
            "SELECT * FROM mail_message_bodies WHERE message_id = ?",
            (normalized_message_id,),
        ),
    )
