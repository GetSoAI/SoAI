"""SoAI - Targeted conversation message mutation transactions [backend/database/repositories/users/message_targeted_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.conversations.conversation_message_storage_validation import (
    validate_messages_payload_for_storage,
)
from core.conversations.conversation_message_write_result import (
    ConversationMessageWriteResult,
)
from core.errors.exceptions import ValidationError
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import is_strict_int
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_versioning import (
    sync_bump_conversation_last_modified_at_ms,
    sync_require_expected_conversation_version,
)
from database.repositories.users.message_assistant_mutation_cleanup import (
    delete_auxiliary_for_assistant_rows,
    select_assistant_rows_for_delete,
)
from database.repositories.users.message_content_integrity import (
    build_message_content_integrity,
)
from database.repositories.users.message_count_sync import sync_count_stored_messages
from database.repositories.users.message_input_mutation_fence import (
    require_message_rows_not_linked_to_active_inputs,
)
from database.repositories.users.message_row_mapping import (
    build_message_payload_from_row,
)

__all__ = (
    "sync_delete_message_by_cursor",
    "sync_resubmit_user_message_by_cursor",
    "sync_truncate_messages_from_cursor",
)


def _require_cursor(created_at_ms: int, message_id: int) -> tuple[int, int]:
    validated_created_at_ms = require_unix_epoch_ms(
        created_at_ms,
        error_message="Message cursor created_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    if not is_strict_int(message_id) or message_id < 0:
        raise ValidationError("Message cursor id must be a non-negative integer.")
    return (validated_created_at_ms, int(message_id))


def _delete_rows_after_cursor(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    created_at_ms: int,
    message_id: int,
    inclusive: bool,
) -> int:
    id_comparator = ">=" if inclusive else ">"
    where_sql = f"(created_at_ms > ? OR (created_at_ms = ? AND id {id_comparator} ?))"
    active_input_where_sql = f"(message.created_at_ms > ? OR (message.created_at_ms = ? AND message.id {id_comparator} ?))"
    params = (created_at_ms, created_at_ms, message_id)
    if (
        conn.execute(
            f"SELECT 1 FROM webui_messages WHERE conv_id = ? AND message_type = 'control' AND {where_sql} LIMIT 1",
            (conv_id, *params),
        ).fetchone()
        is not None
    ):
        raise ValidationError("System-owned control messages cannot be mutated.")
    require_message_rows_not_linked_to_active_inputs(
        conn,
        conv_id=conv_id,
        where_sql=active_input_where_sql,
        params=params,
    )
    assistant_rows = select_assistant_rows_for_delete(
        conn,
        conv_id=conv_id,
        where_sql=where_sql,
        params=params,
    )
    delete_auxiliary_for_assistant_rows(conn, conv_id=conv_id, assistant_rows=assistant_rows)
    cursor = conn.execute(
        f"DELETE FROM webui_messages WHERE conv_id = ? AND {where_sql}",
        (conv_id, *params),
    )
    return int(cursor.rowcount)


def sync_resubmit_user_message_by_cursor(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    created_at_ms: int,
    message_id: int,
    message: JSONDict,
    expected_last_modified_at_ms: int,
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    sync_require_expected_conversation_version(
        conn,
        conv_id=conv_id,
        expected_last_modified_at_ms=expected_last_modified_at_ms,
    )
    cursor_created_at_ms, cursor_message_id = _require_cursor(created_at_ms, message_id)
    validated_messages = validate_messages_payload_for_storage([message])
    if len(validated_messages) != 1:
        raise ValidationError("Message edit requires exactly one message.")
    validated = validated_messages[0]
    if validated.get("role") != "user":
        raise ValidationError("Message edit target must be a user message.")
    if validated.get("message_type") != "chat":
        raise ValidationError("System-owned control messages cannot be edited.")
    if validated.get("created_at_ms") != cursor_created_at_ms:
        raise ValidationError("Edited message timestamp must match the target cursor.")
    content_json = validated.get("content_json")
    if not isinstance(content_json, str):
        raise ValidationError("Edited message content is invalid.")
    content_length, content_sha256 = build_message_content_integrity(content_json)
    now = epoch_ms()
    canonical_row = sync_fetch_one_as_dict(
        conn.execute(
            """
        UPDATE webui_messages
           SET content = ?,
               content_length = ?,
               content_sha256 = ?,
               finalized_at_ms = ?,
               request_id = ?,
               model_id = ?,
               prompt_tokens = ?,
               completion_tokens = ?,
               total_tokens = ?,
               usage_source = ?,
               generation_latency_ms = ?,
               finish_reason = ?,
               thinking_tail_duration_ms = ?
         WHERE conv_id = ? AND id = ? AND created_at_ms = ?
           AND role = 'user' AND message_type = 'chat'
        RETURNING *
        """,
            (
                content_json,
                content_length,
                content_sha256,
                now,
                validated.get("request_id"),
                validated.get("model_id"),
                validated.get("prompt_tokens"),
                validated.get("completion_tokens"),
                validated.get("total_tokens"),
                validated.get("usage_source"),
                validated.get("generation_latency_ms"),
                validated.get("finish_reason"),
                validated.get("thinking_tail_duration_ms"),
                conv_id,
                cursor_message_id,
                cursor_created_at_ms,
            ),
        ),
    )
    if canonical_row is None:
        raise ValidationError("Target user message was not found.")
    _delete_rows_after_cursor(
        conn,
        conv_id=conv_id,
        created_at_ms=cursor_created_at_ms,
        message_id=cursor_message_id,
        inclusive=False,
    )
    return ConversationMessageWriteResult(
        last_modified_at_ms=sync_bump_conversation_last_modified_at_ms(conn, conv_id),
        message_count=sync_count_stored_messages(conn, conv_id),
        canonical_messages=[build_message_payload_from_row(canonical_row)],
    )


def sync_truncate_messages_from_cursor(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    created_at_ms: int,
    message_id: int,
    expected_last_modified_at_ms: int,
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    sync_require_expected_conversation_version(
        conn,
        conv_id=conv_id,
        expected_last_modified_at_ms=expected_last_modified_at_ms,
    )
    cursor_created_at_ms, cursor_message_id = _require_cursor(created_at_ms, message_id)
    target = conn.execute(
        "SELECT message_type FROM webui_messages WHERE conv_id = ? AND created_at_ms = ? AND id = ?",
        (conv_id, cursor_created_at_ms, cursor_message_id),
    ).fetchone()
    if target is not None and target[0] == "control":
        raise ValidationError("System-owned control messages cannot be deleted.")
    deleted = _delete_rows_after_cursor(
        conn,
        conv_id=conv_id,
        created_at_ms=cursor_created_at_ms,
        message_id=cursor_message_id,
        inclusive=True,
    )
    if deleted <= 0:
        raise ValidationError("Target message was not found for truncation.")
    return ConversationMessageWriteResult(
        last_modified_at_ms=sync_bump_conversation_last_modified_at_ms(conn, conv_id),
        message_count=sync_count_stored_messages(conn, conv_id),
    )


def sync_delete_message_by_cursor(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    created_at_ms: int,
    message_id: int,
    expected_last_modified_at_ms: int,
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    sync_require_expected_conversation_version(
        conn,
        conv_id=conv_id,
        expected_last_modified_at_ms=expected_last_modified_at_ms,
    )
    cursor_created_at_ms, cursor_message_id = _require_cursor(created_at_ms, message_id)
    target = conn.execute(
        "SELECT message_type FROM webui_messages WHERE conv_id = ? AND created_at_ms = ? AND id = ?",
        (conv_id, cursor_created_at_ms, cursor_message_id),
    ).fetchone()
    if target is not None and target[0] == "control":
        raise ValidationError("System-owned control messages cannot be deleted.")
    require_message_rows_not_linked_to_active_inputs(
        conn,
        conv_id=conv_id,
        where_sql="message.created_at_ms = ? AND message.id = ?",
        params=(cursor_created_at_ms, cursor_message_id),
    )
    assistant_rows = select_assistant_rows_for_delete(
        conn,
        conv_id=conv_id,
        where_sql="created_at_ms = ? AND id = ?",
        params=(cursor_created_at_ms, cursor_message_id),
    )
    delete_auxiliary_for_assistant_rows(conn, conv_id=conv_id, assistant_rows=assistant_rows)
    cursor = conn.execute(
        "DELETE FROM webui_messages WHERE conv_id = ? AND created_at_ms = ? AND id = ?",
        (conv_id, cursor_created_at_ms, cursor_message_id),
    )
    if cursor.rowcount <= 0:
        raise ValidationError("Target message was not found for deletion.")
    return ConversationMessageWriteResult(
        last_modified_at_ms=sync_bump_conversation_last_modified_at_ms(conn, conv_id),
        message_count=sync_count_stored_messages(conn, conv_id),
    )
