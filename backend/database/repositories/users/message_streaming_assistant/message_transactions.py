"""SoAI - Streaming assistant message write transactions [backend/database/repositories/users/message_streaming_assistant/message_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.conversations.assistant_turn_variant_identity import (
    require_assistant_turn_variant_invariants,
)
from core.conversations.conversation_message_write_result import (
    ConversationMessageWriteResult,
)
from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.validation.epoch import require_unix_epoch_ms
from core.validation.record_fields import require_optional_non_empty_str
from core.validation.requirements import require_non_negative_int
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_versioning import (
    sync_bump_conversation_last_modified_at_ms,
)
from database.repositories.users.message_count_sync import sync_count_stored_messages
from database.repositories.users.message_streaming_assistant.event_transactions import (
    sync_delete_streaming_assistant_event_rows,
)

__all__ = (
    "sync_append_streaming_assistant_placeholder",
    "sync_delete_streaming_assistant_message",
    "sync_update_streaming_assistant_content",
)


def sync_append_streaming_assistant_placeholder(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    created_at_ms: int,
    assistant_turn_at_ms: int,
    request_id: str | None,
    model_id: str | None,
    model_variant_index: int,
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    require_unix_epoch_ms(
        created_at_ms,
        error_message="Streaming assistant created_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    require_unix_epoch_ms(
        assistant_turn_at_ms,
        error_message=(
            "Streaming assistant assistant_turn_at_ms must be an epoch-millisecond integer."
        ),
        enforce_maximum=False,
    )
    existing = conn.execute(
        "SELECT 1 FROM webui_messages WHERE conv_id = ? AND created_at_ms = ?",
        (conv_id, created_at_ms),
    ).fetchone()
    if existing is not None:
        raise ValidationError(
            "Streaming assistant created_at_ms collides with an existing message.",
        )
    latest_row = conn.execute(
        (
            "SELECT created_at_ms FROM webui_messages "
            "WHERE conv_id = ? "
            "ORDER BY created_at_ms DESC, id DESC LIMIT 1"
        ),
        (conv_id,),
    ).fetchone()
    if latest_row is not None:
        latest_value = latest_row[0]
        latest_created_at_ms = require_unix_epoch_ms(
            latest_value,
            error_message=(
                "Stored conversation message created_at_ms must be an epoch-millisecond "
                "integer for streaming."
            ),
            enforce_maximum=False,
        )
        if created_at_ms <= latest_created_at_ms:
            raise ValidationError(
                "Streaming assistant created_at_ms must be strictly greater than existing messages.",
            )
    validated_model_variant_index = require_non_negative_int(
        model_variant_index,
        error_message="Streaming assistant model_variant_index must be a non-negative integer.",
    )
    require_assistant_turn_variant_invariants(
        assistant_at_ms=created_at_ms,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=validated_model_variant_index,
        assistant_turn_after_assistant_error_message=(
            "Streaming assistant assistant_turn_at_ms must not be greater than created_at_ms."
        ),
        canonical_variant_mismatch_error_message=(
            "Streaming assistant canonical variant created_at_ms must equal assistant_turn_at_ms."
        ),
    )
    normalized_request_id = require_optional_non_empty_str(
        request_id,
        label="Streaming assistant request_id",
        build_error=ValidationError,
        invalid_message="Streaming assistant request_id must be non-empty when provided.",
    )
    conn.execute(
        (
            "INSERT INTO webui_messages ("
            "conv_id, role, content, created_at_ms, assistant_turn_at_ms, "
            "model_variant_index, request_id, model_id"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            conv_id,
            "assistant",
            serialize_json_compact_stable_strict(""),
            created_at_ms,
            assistant_turn_at_ms,
            validated_model_variant_index,
            normalized_request_id,
            model_id,
        ),
    )
    last_modified_at_ms = sync_bump_conversation_last_modified_at_ms(conn, conv_id)
    return ConversationMessageWriteResult(
        last_modified_at_ms=last_modified_at_ms,
        message_count=sync_count_stored_messages(conn, conv_id),
    )


def sync_update_streaming_assistant_content(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    created_at_ms: int,
    content_text: str,
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    cursor = conn.execute(
        (
            "UPDATE webui_messages SET content = ? "
            "WHERE conv_id = ? AND created_at_ms = ? AND role = 'assistant' "
            "AND finalized_at_ms IS NULL"
        ),
        (serialize_json_compact_stable_strict(content_text), conv_id, created_at_ms),
    )
    if cursor.rowcount <= 0:
        raise ValidationError("Streaming assistant message not found.")
    last_modified_at_ms = sync_bump_conversation_last_modified_at_ms(conn, conv_id)
    return ConversationMessageWriteResult(
        last_modified_at_ms=last_modified_at_ms,
        message_count=sync_count_stored_messages(conn, conv_id),
    )


def sync_delete_streaming_assistant_message(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    created_at_ms: int,
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    require_unix_epoch_ms(
        created_at_ms,
        error_message="Streaming assistant created_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    sync_delete_streaming_assistant_event_rows(
        conn,
        conv_id=conv_id,
        assistant_at_ms=created_at_ms,
        require_unfinished_assistant=False,
    )
    cursor = conn.execute(
        "DELETE FROM webui_messages WHERE conv_id = ? AND created_at_ms = ? AND role = 'assistant'",
        (conv_id, created_at_ms),
    )
    if cursor.rowcount <= 0:
        raise ValidationError("Streaming assistant message not found.")
    last_modified_at_ms = sync_bump_conversation_last_modified_at_ms(conn, conv_id)
    return ConversationMessageWriteResult(
        last_modified_at_ms=last_modified_at_ms,
        message_count=sync_count_stored_messages(conn, conv_id),
    )
