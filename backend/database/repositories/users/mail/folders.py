"""SoAI - Mail folder repository operations [backend/database/repositories/users/mail/folders.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import DatabaseError
from core.timing.epoch import epoch_ms
from core.users.account_identifier_validation import (
    require_mail_account_id,
    require_mail_folder_id,
)
from core.users.account_identifiers import (
    MAIL_FOLDER_ID_PREFIX,
    build_random_prefixed_identifier,
)
from core.validation.strings import coerce_optional_trimmed_str
from database.core.query_execution import (
    query_one_to_dict,
    query_to_dicts,
    sync_fetch_one_as_dict,
)
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.account_validation import (
    optional_epoch_ms,
    require_bool_int,
    require_nonnegative_int,
    require_text,
    require_user_id,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "read_mail_folder",
    "read_mail_folder_by_remote_mailbox",
    "read_mail_folders",
    "sync_delete_mail_folder",
    "sync_upsert_mail_folder",
)


async def read_mail_folders(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    account_id: str,
) -> list[SQLiteRowDict]:
    return await query_to_dicts(
        database,
        """
        SELECT *
        FROM mail_folders
        WHERE user_id = ? AND mail_account_id = ?
        ORDER BY name COLLATE NOCASE ASC, id ASC
        """,
        (require_user_id(user_id), require_mail_account_id(account_id)),
    )


async def read_mail_folder(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    folder_id: str,
) -> SQLiteRowDict | None:
    return await query_one_to_dict(
        database,
        "SELECT * FROM mail_folders WHERE user_id = ? AND id = ? LIMIT 1",
        (require_user_id(user_id), require_mail_folder_id(folder_id)),
    )


async def read_mail_folder_by_remote_mailbox(
    database: aiosqlite.Connection,
    *,
    user_id: int,
    account_id: str,
    remote_mailbox: str,
) -> SQLiteRowDict | None:
    return await query_one_to_dict(
        database,
        """
        SELECT *
        FROM mail_folders
        WHERE user_id = ? AND mail_account_id = ? AND remote_mailbox = ?
        LIMIT 1
        """,
        (
            require_user_id(user_id),
            require_mail_account_id(account_id),
            require_text(remote_mailbox, "remote_mailbox"),
        ),
    )


def sync_upsert_mail_folder(
    conn: sqlite3.Connection,
    /,
    user_id: int,
    account_id: str,
    payload: JSONDict,
) -> SQLiteRowDict:
    normalized_user_id = require_user_id(user_id)
    normalized_account_id = require_mail_account_id(account_id)
    remote_mailbox = require_text(payload.get("remote_mailbox"), "remote_mailbox")
    try:
        cursor = conn.execute(
            """
            SELECT id, created_at_ms
            FROM mail_folders
            WHERE user_id = ? AND mail_account_id = ? AND remote_mailbox = ?
            LIMIT 1
            """,
            (normalized_user_id, normalized_account_id, remote_mailbox),
        )
        existing = sync_fetch_one_as_dict(cursor)
        now_ms = (
            optional_epoch_ms(payload.get("last_modified_at_ms"), label="last_modified_at_ms")
            or epoch_ms()
        )
        if existing is None:
            folder_id = build_random_prefixed_identifier(MAIL_FOLDER_ID_PREFIX)
            created_at_ms = (
                optional_epoch_ms(payload.get("created_at_ms"), label="created_at_ms") or now_ms
            )
            conn.execute(
                """
                INSERT INTO mail_folders (
                    id, user_id, mail_account_id, remote_mailbox, name, special_use, subscribed,
                    unread_count, message_count, created_at_ms, last_modified_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    folder_id,
                    normalized_user_id,
                    normalized_account_id,
                    remote_mailbox,
                    require_text(payload.get("name"), "name"),
                    coerce_optional_trimmed_str(payload.get("special_use")),
                    require_bool_int(payload.get("subscribed"), "subscribed"),
                    require_nonnegative_int(payload.get("unread_count"), "unread_count"),
                    require_nonnegative_int(payload.get("message_count"), "message_count"),
                    created_at_ms,
                    now_ms,
                ),
            )
            target_folder_id = folder_id
        else:
            target_folder_id = require_mail_folder_id(str(existing["id"]))
            conn.execute(
                """
                UPDATE mail_folders
                SET name = ?, special_use = ?, subscribed = ?, unread_count = ?, message_count = ?, last_modified_at_ms = ?
                WHERE user_id = ? AND id = ?
                """,
                (
                    require_text(payload.get("name"), "name"),
                    coerce_optional_trimmed_str(payload.get("special_use")),
                    require_bool_int(payload.get("subscribed"), "subscribed"),
                    require_nonnegative_int(payload.get("unread_count"), "unread_count"),
                    require_nonnegative_int(payload.get("message_count"), "message_count"),
                    now_ms,
                    normalized_user_id,
                    target_folder_id,
                ),
            )
        record = sync_fetch_one_as_dict(
            conn.execute(
                "SELECT * FROM mail_folders WHERE user_id = ? AND id = ?",
                (normalized_user_id, target_folder_id),
            ),
        )
        if record is None:
            raise DatabaseError("Failed to read mail folder.")
        return record
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        raise DatabaseError(
            "Failed to upsert mail folder.",
            details={"constraint_type": constraint_type, "detail": detail},
        ) from exception


def sync_delete_mail_folder(conn: sqlite3.Connection, /, user_id: int, folder_id: str) -> bool:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM mail_folders WHERE user_id = ? AND id = ?",
            (require_user_id(user_id), require_mail_folder_id(folder_id)),
        )
        return cursor.rowcount > 0
    finally:
        cursor.close()
