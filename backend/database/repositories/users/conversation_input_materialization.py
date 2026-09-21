"""SoAI - Claimed conversation input materialization [backend/database/repositories/users/conversation_input_materialization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError, StateError
from core.timing.epoch import epoch_ms
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_input_materialization_write import (
    sync_materialize_conversation_input_user_message,
)
from database.repositories.users.conversation_input_row_mapping import format_conversation_input_row
from database.repositories.users.conversation_stream_cancellation_state import (
    sync_has_chat_stream_cancellation_receipt,
)

if TYPE_CHECKING:
    from core.plugins.protocols_instance import FilesProtocol
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("sync_materialize_claimed_conversation_input",)


def _require_claim(
    row: JSONDict,
    *,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
) -> None:
    if row.get("claim_generation") != claim_generation:
        raise ConflictError("Conversation input claim generation changed.")
    if row.get("claim_owner") != claim_owner:
        raise ConflictError("Conversation input claim owner changed.")
    if row.get("claim_server_boot_id") != server_boot_id:
        raise ConflictError("Conversation input server boot changed.")


def _require_current_conversation_generation(
    sqlite_conn: sqlite3.Connection,
    row: JSONDict,
) -> None:
    conv_id = row.get("conv_id")
    user_id = row.get("user_id")
    generation = row.get("conversation_generation")
    current = sqlite_conn.execute(
        """
        SELECT input_generation
        FROM webui_conversations
        WHERE id = ? AND user_id = ?
        LIMIT 1
        """,
        (conv_id, user_id),
    ).fetchone()
    if current is None or not is_strict_int(current[0]):
        raise ConflictError("Conversation input owner no longer exists.")
    if current[0] != generation:
        raise ConflictError("Conversation input generation changed.")


def _existing_materialization_result(row: JSONDict, request_id: str) -> JSONDict:
    if row.get("state") != "running" or row.get("request_id") != request_id:
        raise ConflictError("Conversation input is not materializable.")
    if not is_strict_int(row.get("materialized_message_id")):
        raise StateError("Running conversation input is missing its user message.")
    result = dict(row)
    result["was_materialized"] = False
    return result


def sync_materialize_claimed_conversation_input(
    sqlite_conn: sqlite3.Connection,
    input_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    request_id: str,
    storage_root: str | None = None,
    files: FilesProtocol | None = None,
) -> JSONDict:
    stored = read_conversation_input_by_input_id_global(sqlite_conn, input_id)
    formatted = format_conversation_input_row(stored)
    if formatted is None:
        raise ConflictError("Conversation input not found.")
    _require_claim(
        formatted,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
    )
    _require_current_conversation_generation(sqlite_conn, formatted)
    if formatted.get("state") != "materializing":
        return _existing_materialization_result(formatted, request_id)
    if formatted.get("input_type") not in {"prompt", "steer"}:
        raise ConflictError("Conversation input type cannot materialize a user message.")
    conv_id = formatted.get("conv_id")
    user_id = formatted.get("user_id")
    text = formatted.get("text")
    attachment_content = formatted.get("attachment_content")
    if not isinstance(conv_id, str) or not is_strict_int(user_id):
        raise StateError("Conversation input ownership is invalid.")
    if sync_has_chat_stream_cancellation_receipt(
        sqlite_conn,
        int(user_id),
        conv_id,
        request_id,
    ):
        cancellation_result = dict(formatted)
        cancellation_result["was_materialized"] = False
        cancellation_result["cancellation_accepted"] = True
        return cancellation_result
    if not isinstance(text, str) or not isinstance(attachment_content, list):
        raise StateError("Conversation input content is invalid.")
    source_metadata = formatted.get("source_metadata")
    transport_origin = formatted.get("transport_origin")
    if not isinstance(source_metadata, dict) or not isinstance(transport_origin, str):
        raise StateError("Conversation input source identity is invalid.")
    messaging_sender_display_name = (
        coerce_optional_trimmed_str(source_metadata.get("sender_display_name"))
        if transport_origin == "messaging"
        else None
    )
    messaging_sender_id = (
        coerce_optional_trimmed_str(source_metadata.get("sender_id"))
        if transport_origin == "messaging"
        else None
    )
    materialized_at_ms = epoch_ms()
    materialization = sync_materialize_conversation_input_user_message(
        sqlite_conn,
        conv_id=conv_id,
        user_id=int(user_id),
        input_id=input_id,
        text=text,
        attachment_content=attachment_content,
        messaging_sender_display_name=messaging_sender_display_name,
        messaging_sender_id=messaging_sender_id,
        set_default_title=transport_origin == "chat",
        storage_root=storage_root,
        files=files,
    )
    assistant_at_ms = materialization.message_at_ms + 1
    cursor = sqlite_conn.execute(
        """
        UPDATE webui_conversation_inputs
        SET state = 'running', materialized_message_id = ?,
            materialized_message_at_ms = ?, request_id = ?, assistant_at_ms = ?,
            assistant_turn_at_ms = ?, model_variant_index = 0,
            materialized_at_ms = ?, running_at_ms = ?, updated_at_ms = ?
        WHERE input_id = ? AND state = 'materializing'
          AND claim_generation = ? AND claim_owner = ? AND claim_server_boot_id = ?
          AND conversation_generation = (
              SELECT input_generation
              FROM webui_conversations
              WHERE id = webui_conversation_inputs.conv_id
                AND user_id = webui_conversation_inputs.user_id
          )
        RETURNING *
        """,
        (
            materialization.message_id,
            materialization.message_at_ms,
            request_id,
            assistant_at_ms,
            assistant_at_ms,
            materialized_at_ms,
            materialized_at_ms,
            materialized_at_ms,
            input_id,
            claim_generation,
            claim_owner,
            server_boot_id,
        ),
    )
    updated = sync_fetch_one_as_dict(cursor)
    result = format_conversation_input_row(updated)
    if result is None:
        raise ConflictError("Conversation input materialization fence changed.")
    result["was_materialized"] = True
    result["conversation_last_modified_at_ms"] = materialization.write_result.last_modified_at_ms
    result["message_count"] = materialization.write_result.message_count
    result["materialized_message"] = materialization.message
    if materialization.conversation_title is not None:
        result["conversation_title"] = materialization.conversation_title
    if materialization.write_result.knowledge_attachment_summaries:
        result["knowledge_attachment_summaries"] = (
            materialization.write_result.knowledge_attachment_summaries
        )
    return result


def read_conversation_input_by_input_id_global(
    sqlite_conn: sqlite3.Connection,
    input_id: str,
) -> SQLiteRowDict | None:
    return sync_fetch_one_as_dict(
        sqlite_conn.execute(
            "SELECT * FROM webui_conversation_inputs WHERE input_id = ? LIMIT 1",
            (input_id,),
        ),
    )
