"""SoAI - Streaming assistant event write transactions [backend/database/repositories/users/message_streaming_assistant/event_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.conversations.conversation_message_write_result import (
    ConversationMessageWriteResult,
)
from core.errors.exceptions import ValidationError
from core.validation.epoch import require_unix_epoch_ms
from core.validation.integers import is_strict_int
from database.repositories.users.assistant_event_chronology_validation import (
    is_terminal_tool_event_unique_integrity_error,
    raise_duplicate_terminal_tool_event,
    resolve_assistant_event_chronology,
    resolve_persisted_assistant_visible_length,
    validate_unique_terminal_tool_event,
)
from database.repositories.users.assistant_event_sequence import (
    resolve_next_assistant_event_sequence,
)
from database.repositories.users.assistant_tool_event_payload_validation import (
    build_validated_assistant_event_payload_json,
)
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_versioning import (
    sync_bump_conversation_last_modified_at_ms,
    sync_load_conversation_last_modified_at_ms,
)
from database.repositories.users.message_count_sync import sync_count_stored_messages

__all__ = (
    "sync_append_streaming_assistant_events_batch",
    "sync_delete_streaming_assistant_event_rows",
    "sync_delete_streaming_assistant_events",
)


def sync_append_streaming_assistant_events_batch(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    assistant_at_ms: int,
    events: list[tuple[int, int, str, str, int]],
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    require_unix_epoch_ms(
        assistant_at_ms,
        error_message="Assistant event assistant_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    if not events:
        return ConversationMessageWriteResult(
            last_modified_at_ms=sync_load_conversation_last_modified_at_ms(conn, conv_id),
            message_count=sync_count_stored_messages(conn, conv_id),
        )
    expected_sequence = resolve_next_assistant_event_sequence(
        conn,
        conv_id=conv_id,
        assistant_at_ms=assistant_at_ms,
    )
    current_sequence = expected_sequence
    running_visible_length = resolve_persisted_assistant_visible_length(
        conn,
        conv_id=conv_id,
        assistant_at_ms=assistant_at_ms,
    )
    terminal_tool_event_keys: set[str] = set()
    rows_to_insert: list[tuple[str, int, int, int, str, str, int]] = []
    for sequence, assistant_revision, event_type, payload_json, created_at_ms in events:
        if not is_strict_int(sequence) or sequence < 0:
            raise ValidationError("Assistant event sequence must be a non-negative integer.")
        if sequence < expected_sequence:
            continue
        if sequence != current_sequence:
            raise ValidationError(
                "Assistant event sequence must be contiguous starting at the next expected sequence.",
            )
        if (
            isinstance(assistant_revision, bool)
            or not isinstance(assistant_revision, int)
            or assistant_revision <= 0
        ):
            raise ValidationError("Assistant event assistant_revision must be a positive integer.")
        if assistant_revision != (sequence + 1):
            raise ValidationError("Assistant event assistant_revision must equal sequence + 1.")
        if not isinstance(event_type, str) or not event_type.strip():
            raise ValidationError("Assistant event type must be a non-empty string.")
        if not isinstance(payload_json, str) or not payload_json.strip():
            raise ValidationError("Assistant event payload_json must be a non-empty JSON string.")
        require_unix_epoch_ms(
            created_at_ms,
            error_message="Assistant event created_at_ms must be an epoch-millisecond integer.",
            enforce_maximum=False,
        )
        normalized_event_type = event_type.strip()
        terminal_tool_event_key = validate_unique_terminal_tool_event(
            conn=conn,
            conv_id=conv_id,
            assistant_at_ms=assistant_at_ms,
            event_type=normalized_event_type,
            payload_json=payload_json,
        )
        if terminal_tool_event_key is not None:
            if terminal_tool_event_key in terminal_tool_event_keys:
                raise ValidationError(
                    "Assistant timeline batch contains duplicate terminal tool events.",
                )
            terminal_tool_event_keys.add(terminal_tool_event_key)
        chronology_result = resolve_assistant_event_chronology(
            event_type=normalized_event_type,
            payload_json=payload_json,
            running_visible_length=running_visible_length,
        )
        validated_payload_json = build_validated_assistant_event_payload_json(
            event_type=normalized_event_type,
            payload_json=chronology_result.payload_json,
        )
        running_visible_length = chronology_result.running_visible_length
        rows_to_insert.append(
            (
                conv_id,
                assistant_at_ms,
                sequence,
                assistant_revision,
                normalized_event_type,
                validated_payload_json,
                created_at_ms,
            ),
        )
        current_sequence += 1
    if not rows_to_insert:
        return ConversationMessageWriteResult(
            last_modified_at_ms=sync_load_conversation_last_modified_at_ms(conn, conv_id),
            message_count=sync_count_stored_messages(conn, conv_id),
        )
    try:
        conn.executemany(
            """
            INSERT INTO webui_assistant_message_events (
                conv_id,
                assistant_at_ms,
                sequence,
                assistant_revision,
                event_type,
                payload_json,
                created_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows_to_insert,
        )
    except sqlite3.IntegrityError as exception:
        if is_terminal_tool_event_unique_integrity_error(exception):
            raise_duplicate_terminal_tool_event()
        raise
    last_modified_at_ms = sync_bump_conversation_last_modified_at_ms(conn, conv_id)
    return ConversationMessageWriteResult(
        last_modified_at_ms=last_modified_at_ms,
        message_count=sync_count_stored_messages(conn, conv_id),
    )


def sync_delete_streaming_assistant_event_rows(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
    require_unfinished_assistant: bool,
) -> None:
    if require_unfinished_assistant:
        resolve_next_assistant_event_sequence(
            conn,
            conv_id=conv_id,
            assistant_at_ms=assistant_at_ms,
        )
    conn.execute(
        "DELETE FROM webui_assistant_message_events WHERE conv_id = ? AND assistant_at_ms = ?",
        (conv_id, assistant_at_ms),
    )


def sync_delete_streaming_assistant_events(
    conn: sqlite3.Connection,
    conv_id: str,
    user_id: int,
    assistant_at_ms: int,
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, conv_id, user_id)
    require_unix_epoch_ms(
        assistant_at_ms,
        error_message="Streaming assistant assistant_at_ms must be an epoch-millisecond integer.",
        enforce_maximum=False,
    )
    sync_delete_streaming_assistant_event_rows(
        conn,
        conv_id=conv_id,
        assistant_at_ms=assistant_at_ms,
        require_unfinished_assistant=True,
    )
    last_modified_at_ms = sync_bump_conversation_last_modified_at_ms(conn, conv_id)
    return ConversationMessageWriteResult(
        last_modified_at_ms=last_modified_at_ms,
        message_count=sync_count_stored_messages(conn, conv_id),
    )
