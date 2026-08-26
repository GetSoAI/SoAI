"""SoAI - Conversation input user-message materialization [backend/database/repositories/users/conversation_input_materialization_write.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.conversations.default_title_resolution import (
    resolve_default_title_from_user_message,
)
from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int
from database.repositories.users.conversation_input_attachment_semantics import (
    build_expected_user_message_content,
)
from database.repositories.users.message_row_mapping import build_message_payload_from_row
from database.repositories.users.message_write_transactions import sync_append_messages

if TYPE_CHECKING:
    from core.conversations.conversation_message_write_result import ConversationMessageWriteResult
    from core.plugins.protocols_instance import FilesProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "ConversationInputMessageMaterialization",
    "sync_materialize_conversation_input_user_message",
)


class ConversationInputMessageMaterialization:
    def __init__(
        self,
        *,
        message_id: int,
        message_at_ms: int,
        message: JSONDict,
        write_result: ConversationMessageWriteResult,
        conversation_title: str | None,
    ) -> None:
        self.message_id = message_id
        self.message_at_ms = message_at_ms
        self.message = message
        self.write_result = write_result
        self.conversation_title = conversation_title


def _next_message_timestamp(sqlite_conn: sqlite3.Connection, conv_id: str) -> int:
    row = sqlite_conn.execute(
        """
        SELECT created_at_ms
        FROM webui_messages
        WHERE conv_id = ?
        ORDER BY created_at_ms DESC, id DESC
        LIMIT 1
        """,
        (conv_id,),
    ).fetchone()
    current_ms = epoch_ms()
    if row is None:
        return current_ms
    latest_value = row[0]
    if not is_strict_int(latest_value):
        raise StateError("Conversation latest message timestamp is invalid.")
    return max(current_ms, int(latest_value) + 1)


def sync_materialize_conversation_input_user_message(
    sqlite_conn: sqlite3.Connection,
    *,
    conv_id: str,
    user_id: int,
    input_id: str,
    text: str,
    attachment_content: list[JSONValue],
    messaging_sender_display_name: str | None,
    messaging_sender_id: str | None,
    set_default_title: bool,
    storage_root: str | None,
    files: FilesProtocol | None,
) -> ConversationInputMessageMaterialization:
    message_at_ms = _next_message_timestamp(sqlite_conn, conv_id)
    message_content = build_expected_user_message_content(text, attachment_content)
    write_result = sync_append_messages(
        sqlite_conn,
        conv_id,
        user_id,
        [{"role": "user", "content": message_content, "timestamp": message_at_ms}],
        None,
        storage_root,
        files,
        conversation_input_id=input_id,
        soai_path_resolved_at_ms=message_at_ms,
    )
    row = sqlite_conn.execute(
        """
        SELECT *, ? AS conversation_input_id,
               ? AS messaging_sender_display_name,
               ? AS messaging_sender_id
        FROM webui_messages
        WHERE conv_id = ? AND role = 'user' AND created_at_ms = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (
            input_id,
            messaging_sender_display_name,
            messaging_sender_id,
            conv_id,
            message_at_ms,
        ),
    ).fetchone()
    if row is None or not is_strict_int(row["id"]):
        raise StateError("Materialized conversation input message is missing.")
    message = build_message_payload_from_row(dict(row))
    conversation_title = None
    if set_default_title and write_result.message_count == 1:
        conversation_title = resolve_default_title_from_user_message(message)
        updated = sqlite_conn.execute(
            "UPDATE webui_conversations SET title = ? WHERE id = ? AND user_id = ?",
            (conversation_title, conv_id, user_id),
        )
        if updated.rowcount != 1:
            raise StateError("Materialized conversation input title update failed.")
    return ConversationInputMessageMaterialization(
        message_id=int(row["id"]),
        message_at_ms=message_at_ms,
        message=message,
        write_result=write_result,
        conversation_title=conversation_title,
    )
