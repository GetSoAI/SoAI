"""SoAI - Conversation draft read queries [backend/database/repositories/users/conversation_draft_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.attachments.attachment_content_parts import content_part_from_file_attachment
from core.conversations.conversation_draft_state import ConversationDraftState
from core.errors.exceptions import StateError
from database.core.query_execution import query_one_to_dict, sync_fetch_one_as_dict
from database.core.sqlite_row_scalars import require_sqlite_row_int
from database.repositories.users.conversation_attachment_file_lookup import (
    fetch_file_attachment_by_id,
)
from database.repositories.users.conversation_attachment_rows import (
    format_attachment_row,
)
from database.repositories.users.conversation_draft_row_mapping import (
    format_conversation_draft_row,
    parse_conversation_draft_attachment_json,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "async_query_conversation_draft_state",
    "query_conversation_draft_state",
)


def _fetch_draft_row(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> SQLiteRowDict | None:
    return sync_fetch_one_as_dict(
        conn.execute(
            """
            SELECT *
            FROM webui_conversation_drafts
            WHERE conv_id = ? AND user_id = ?
            """,
            (conv_id, user_id),
        ),
    )


def _restorable_attachment(row: JSONDict | None) -> JSONDict | None:
    if row is None:
        return None
    if row.get("state") != "staged" or row.get("parse_state") != "ready":
        return None
    return row


def _draft_file_attachment(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    entry: JSONDict,
) -> JSONDict | None:
    attachment_id = entry.get("attachment_id")
    if not isinstance(attachment_id, str) or not attachment_id:
        return None
    return _restorable_attachment(
        fetch_file_attachment_by_id(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            attachment_id=attachment_id,
        ),
    )


async def _async_fetch_draft_row(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
) -> SQLiteRowDict | None:
    return await query_one_to_dict(
        database,
        """
        SELECT *
        FROM webui_conversation_drafts
        WHERE conv_id = ? AND user_id = ?
        """,
        (conv_id, user_id),
    )


async def _async_draft_file_attachment(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
    entry: JSONDict,
) -> JSONDict | None:
    attachment_id = entry.get("attachment_id")
    if not isinstance(attachment_id, str) or not attachment_id:
        return None
    row = await query_one_to_dict(
        database,
        """
        SELECT *
        FROM webui_conversation_attachments
        WHERE conv_id = ? AND user_id = ? AND id = ?
        """,
        (conv_id, user_id, attachment_id),
    )
    return _restorable_attachment(format_attachment_row(row))


def _hydrate_draft_content(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    entries: list[JSONValue],
) -> tuple[list[JSONValue], list[JSONDict], int]:
    hydrated_entries: list[JSONValue] = []
    attachments: list[JSONDict] = []
    dropped_count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise StateError("Validated draft entry is not an object.")
        if entry.get("type") == "soai_path_record":
            hydrated_entries.append(dict(entry))
            continue
        if entry.get("type") != "soai_file":
            raise StateError("Validated draft entry type is unsupported.")
        attachment = _draft_file_attachment(
            conn,
            conv_id=conv_id,
            user_id=user_id,
            entry=entry,
        )
        if attachment is None:
            dropped_count += 1
            continue
        hydrated_entries.append(content_part_from_file_attachment(attachment))
        attachments.append(attachment)
    return hydrated_entries, attachments, dropped_count


async def _async_hydrate_draft_content(
    database: aiosqlite.Connection,
    *,
    conv_id: str,
    user_id: int,
    entries: list[JSONValue],
) -> tuple[list[JSONValue], list[JSONDict], int]:
    hydrated_entries: list[JSONValue] = []
    attachments: list[JSONDict] = []
    dropped_count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise StateError("Validated draft entry is not an object.")
        if entry.get("type") == "soai_path_record":
            hydrated_entries.append(dict(entry))
            continue
        if entry.get("type") != "soai_file":
            raise StateError("Validated draft entry type is unsupported.")
        attachment = await _async_draft_file_attachment(
            database,
            conv_id=conv_id,
            user_id=user_id,
            entry=entry,
        )
        if attachment is None:
            dropped_count += 1
            continue
        hydrated_entries.append(content_part_from_file_attachment(attachment))
        attachments.append(attachment)
    return hydrated_entries, attachments, dropped_count


def query_conversation_draft_state(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
) -> ConversationDraftState:
    row = _fetch_draft_row(conn, conv_id=conv_id, user_id=user_id)
    if row is None:
        return ConversationDraftState(draft=None, revision=0)
    revision = require_sqlite_row_int(
        row, "revision", label="Conversation draft revision", minimum=1
    )
    is_deleted = require_sqlite_row_int(
        row, "is_deleted", label="Conversation draft deletion state", minimum=0
    )
    if is_deleted > 1:
        raise StateError("Conversation draft deletion state is invalid.")
    if is_deleted == 1:
        return ConversationDraftState(draft=None, revision=revision)
    raw_attachment_content = row.get("attachment_content_json")
    if not isinstance(raw_attachment_content, str):
        raise StateError("Conversation draft attachment_content_json is invalid.")
    entries = parse_conversation_draft_attachment_json(raw_attachment_content)
    hydrated_entries, attachments, dropped_count = _hydrate_draft_content(
        conn,
        conv_id=conv_id,
        user_id=user_id,
        entries=entries,
    )
    return ConversationDraftState(
        draft=format_conversation_draft_row(
            row,
            attachment_content=hydrated_entries,
            attachments=attachments,
            dropped_attachment_count=dropped_count,
        ),
        revision=revision,
    )


async def async_query_conversation_draft_state(
    database: aiosqlite.Connection,
    conv_id: str,
    user_id: int,
) -> ConversationDraftState:
    row = await _async_fetch_draft_row(database, conv_id=conv_id, user_id=user_id)
    if row is None:
        return ConversationDraftState(draft=None, revision=0)
    revision = require_sqlite_row_int(
        row, "revision", label="Conversation draft revision", minimum=1
    )
    is_deleted = require_sqlite_row_int(
        row, "is_deleted", label="Conversation draft deletion state", minimum=0
    )
    if is_deleted > 1:
        raise StateError("Conversation draft deletion state is invalid.")
    if is_deleted == 1:
        return ConversationDraftState(draft=None, revision=revision)
    raw_attachment_content = row.get("attachment_content_json")
    if not isinstance(raw_attachment_content, str):
        raise StateError("Conversation draft attachment_content_json is invalid.")
    entries = parse_conversation_draft_attachment_json(raw_attachment_content)
    hydrated_entries, attachments, dropped_count = await _async_hydrate_draft_content(
        database,
        conv_id=conv_id,
        user_id=user_id,
        entries=entries,
    )
    return ConversationDraftState(
        draft=format_conversation_draft_row(
            row,
            attachment_content=hydrated_entries,
            attachments=attachments,
            dropped_attachment_count=dropped_count,
        ),
        revision=revision,
    )
