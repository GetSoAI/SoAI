"""SoAI - Mail message repository read operations [backend/database/repositories/users/mail/message_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from core.users.account_identifier_validation import (
    require_mail_attachment_id,
    require_mail_folder_id,
    require_mail_message_id,
)
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.account_validation import require_user_id

__all__ = (
    "read_mail_attachment_part",
    "read_mail_message",
    "read_mail_message_body",
    "read_mail_message_parts",
    "read_mail_messages",
)


async def read_mail_messages(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    folder_id: str,
) -> list[SQLiteRowDict]:
    return await query_to_dicts(
        database,
        """
        SELECT *
        FROM mail_messages
        WHERE user_id = ? AND folder_id = ?
        ORDER BY received_at_ms DESC, id DESC
        """,
        (require_user_id(user_id), require_mail_folder_id(folder_id)),
    )


async def read_mail_message(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    message_id: str,
) -> SQLiteRowDict | None:
    return await query_one_to_dict(
        database,
        "SELECT * FROM mail_messages WHERE user_id = ? AND id = ? LIMIT 1",
        (require_user_id(user_id), require_mail_message_id(message_id)),
    )


async def read_mail_message_body(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    message_id: str,
) -> SQLiteRowDict | None:
    return await query_one_to_dict(
        database,
        """
        SELECT body.*
        FROM mail_message_bodies AS body
        INNER JOIN mail_messages AS message ON message.id = body.message_id
        WHERE message.user_id = ? AND body.message_id = ?
        LIMIT 1
        """,
        (require_user_id(user_id), require_mail_message_id(message_id)),
    )


async def read_mail_message_parts(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    message_id: str,
) -> list[SQLiteRowDict]:
    return await query_to_dicts(
        database,
        """
        SELECT part.*
        FROM mail_message_parts AS part
        INNER JOIN mail_messages AS message ON message.id = part.message_id
        WHERE message.user_id = ? AND part.message_id = ?
        ORDER BY part.part_id ASC
        """,
        (require_user_id(user_id), require_mail_message_id(message_id)),
    )


async def read_mail_attachment_part(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    attachment_id: str,
) -> SQLiteRowDict | None:
    return await query_one_to_dict(
        database,
        """
        SELECT part.*
        FROM mail_message_parts AS part
        INNER JOIN mail_messages AS message ON message.id = part.message_id
        WHERE message.user_id = ? AND part.attachment_id = ?
        LIMIT 1
        """,
        (require_user_id(user_id), require_mail_attachment_id(attachment_id)),
    )
