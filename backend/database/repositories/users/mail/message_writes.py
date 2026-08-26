"""SoAI - Mail message repository write operations [backend/database/repositories/users/mail/message_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import DatabaseError
from core.users.account_identifier_validation import (
    require_mail_account_id,
    require_mail_folder_id,
    require_mail_message_id,
)
from core.users.account_identifiers import (
    MAIL_MESSAGE_ID_PREFIX,
    build_random_prefixed_identifier,
)
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sql_builders import build_placeholder_list, build_update_statement
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.core.sqlite_values import SQLiteRowDict
from database.repositories.users.account_validation import (
    require_nonnegative_int,
    require_text,
    require_user_id,
)
from database.repositories.users.mail.message_row_builders import (
    MailMessageIdentity,
    build_message_row,
    build_message_updates,
    resolve_message_identity,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_delete_mail_message",
    "sync_delete_mail_messages",
    "sync_update_mail_message",
    "sync_upsert_mail_message",
)

_ALLOWED_MESSAGE_UPDATE_COLUMNS: frozenset[str] = frozenset(
    {
        "folder_id",
        "subject",
        "snippet",
        "unread",
        "flagged",
        "has_attachments",
        "attachment_count",
        "deleted_original_folder_id",
        "invite_json",
        "last_modified_at_ms",
    },
)


def sync_upsert_mail_message(
    conn: sqlite3.Connection,
    /,
    user_id: int,
    account_id: str,
    folder_id: str,
    payload: JSONDict,
) -> SQLiteRowDict:
    normalized_user_id = require_user_id(user_id)
    normalized_account_id = require_mail_account_id(account_id)
    identity = resolve_message_identity(payload)
    row = build_message_row(
        user_id=normalized_user_id,
        account_id=normalized_account_id,
        folder_id=folder_id,
        payload=payload,
    )
    try:
        existing_id = _find_existing_message_id(
            conn,
            account_id=normalized_account_id,
            identity=identity,
        )
        if existing_id is None:
            row["id"] = build_random_prefixed_identifier(MAIL_MESSAGE_ID_PREFIX)
            conn.execute(
                """
                INSERT INTO mail_messages (
                    id, user_id, mail_account_id, folder_id, remote_mailbox, uidvalidity, uid,
                    uidl, thread_id, rfc822_message_id, in_reply_to_message_id, references_json,
                    subject, from_json, to_json, cc_json, bcc_json, sent_at_ms, received_at_ms,
                    snippet, size_bytes, unread, flagged, has_attachments, attachment_count,
                    deleted_original_folder_id, invite_json, created_at_ms, last_modified_at_ms
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                """,
                (
                    row["id"],
                    row["user_id"],
                    row["mail_account_id"],
                    row["folder_id"],
                    row["remote_mailbox"],
                    row["uidvalidity"],
                    row["uid"],
                    row["uidl"],
                    row["thread_id"],
                    row["rfc822_message_id"],
                    row["in_reply_to_message_id"],
                    row["references_json"],
                    row["subject"],
                    row["from_json"],
                    row["to_json"],
                    row["cc_json"],
                    row["bcc_json"],
                    row["sent_at_ms"],
                    row["received_at_ms"],
                    row["snippet"],
                    row["size_bytes"],
                    row["unread"],
                    row["flagged"],
                    row["has_attachments"],
                    row["attachment_count"],
                    row["deleted_original_folder_id"],
                    row["invite_json"],
                    row["created_at_ms"],
                    row["last_modified_at_ms"],
                ),
            )
            target_message_id = require_mail_message_id(str(row["id"]))
        else:
            target_message_id = existing_id
            updates = dict(row)
            updates.pop("user_id", None)
            updates.pop("mail_account_id", None)
            updates.pop("created_at_ms", None)
            updates.pop("id", None)
            sql, params = build_update_statement(
                table="mail_messages",
                updates=updates,
                where_clause="user_id = ? AND id = ?",
                where_params=(normalized_user_id, target_message_id),
            )
            conn.execute(sql, params)
        record = sync_fetch_one_as_dict(
            conn.execute(
                "SELECT * FROM mail_messages WHERE user_id = ? AND id = ?",
                (normalized_user_id, target_message_id),
            ),
        )
        if record is None:
            raise DatabaseError("Failed to read mail message.")
        return record
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        raise DatabaseError(
            "Failed to upsert mail message.",
            details={"constraint_type": constraint_type, "detail": detail},
        ) from exception


def sync_update_mail_message(
    conn: sqlite3.Connection,
    /,
    user_id: int,
    message_id: str,
    updates: JSONDict,
) -> SQLiteRowDict | None:
    mapped = build_message_updates(updates)
    sql, params = build_update_statement(
        table="mail_messages",
        updates=mapped,
        where_clause="user_id = ? AND id = ?",
        where_params=(require_user_id(user_id), require_mail_message_id(message_id)),
        allowed_columns=_ALLOWED_MESSAGE_UPDATE_COLUMNS,
    )
    cursor = conn.execute(sql, params)
    try:
        updated_rows = cursor.rowcount
    finally:
        cursor.close()
    if updated_rows <= 0:
        return None
    return sync_fetch_one_as_dict(
        conn.execute(
            "SELECT * FROM mail_messages WHERE user_id = ? AND id = ?",
            (require_user_id(user_id), require_mail_message_id(message_id)),
        ),
    )


def sync_delete_mail_message(conn: sqlite3.Connection, /, user_id: int, message_id: str) -> bool:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM mail_messages WHERE user_id = ? AND id = ?",
            (require_user_id(user_id), require_mail_message_id(message_id)),
        )
        return cursor.rowcount > 0
    finally:
        cursor.close()


def sync_delete_mail_messages(
    conn: sqlite3.Connection,
    /,
    user_id: int,
    folder_id: str,
    message_ids: list[str],
) -> int:
    normalized_user_id = require_user_id(user_id)
    normalized_folder_id = require_mail_folder_id(folder_id)
    normalized_message_ids = [require_mail_message_id(message_id) for message_id in message_ids]
    if not normalized_message_ids:
        return 0
    placeholders = build_placeholder_list(len(normalized_message_ids))
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"""
            DELETE FROM mail_messages
            WHERE user_id = ? AND folder_id = ? AND id IN ({placeholders})
            """,
            (normalized_user_id, normalized_folder_id, *normalized_message_ids),
        )
        return int(cursor.rowcount)
    finally:
        cursor.close()


def _find_existing_message_id(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    identity: MailMessageIdentity,
) -> str | None:
    if identity.protocol == "pop3":
        cursor = conn.execute(
            "SELECT id FROM mail_messages WHERE mail_account_id = ? AND uidl = ? LIMIT 1",
            (account_id, require_text(identity.uidl, "uidl")),
        )
    else:
        cursor = conn.execute(
            """
            SELECT id
            FROM mail_messages
            WHERE mail_account_id = ? AND remote_mailbox = ? AND uidvalidity = ? AND uid = ?
            LIMIT 1
            """,
            (
                account_id,
                require_text(identity.remote_mailbox, "remote_mailbox"),
                require_nonnegative_int(identity.uidvalidity, "uidvalidity"),
                require_nonnegative_int(identity.uid, "uid"),
            ),
        )
    record = sync_fetch_one_as_dict(cursor)
    if record is None:
        return None
    raw_id = record.get("id")
    return require_mail_message_id(str(raw_id))
