"""SoAI - Persistence helpers for assistant message event timeline [backend/database/repositories/users/message_assistant_event_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ValidationError
from database.repositories.users.assistant_event_chronology_validation import (
    is_terminal_tool_event_unique_integrity_error,
    raise_duplicate_terminal_tool_event,
    resolve_assistant_event_chronology,
    resolve_persisted_assistant_visible_length,
    validate_unique_terminal_tool_event,
)
from database.repositories.users.assistant_event_field_validation import (
    validate_assistant_event_assistant_revision,
    validate_assistant_event_epoch_timestamp,
    validate_assistant_event_sequence,
    validate_assistant_event_type,
)
from database.repositories.users.assistant_event_sequence import (
    resolve_next_assistant_event_sequence,
)
from database.repositories.users.assistant_tool_event_payload_validation import (
    build_validated_assistant_event_payload_json,
)

__all__ = ("sync_append_streaming_assistant_event_row",)


def sync_append_streaming_assistant_event_row(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
    sequence: int,
    assistant_revision: int,
    event_type: str,
    payload_json: str,
    created_at_ms: int,
) -> None:
    validated_timestamp = validate_assistant_event_epoch_timestamp(
        assistant_at_ms,
        field_name="assistant_at_ms",
    )
    validated_sequence = validate_assistant_event_sequence(sequence)
    validated_assistant_revision = validate_assistant_event_assistant_revision(assistant_revision)
    validated_event_type = validate_assistant_event_type(event_type)
    if not isinstance(payload_json, str) or not payload_json.strip():
        raise ValidationError("Assistant event payload_json must be a non-empty JSON string.")
    validated_created_at_ms = validate_assistant_event_epoch_timestamp(
        created_at_ms,
        field_name="created_at_ms",
    )
    expected_sequence = resolve_next_assistant_event_sequence(
        conn,
        conv_id=conv_id,
        assistant_at_ms=validated_timestamp,
    )
    if validated_sequence != expected_sequence:
        raise ValidationError("Assistant event sequence must be contiguous starting at 0.")
    running_visible_length = resolve_persisted_assistant_visible_length(
        conn,
        conv_id=conv_id,
        assistant_at_ms=validated_timestamp,
    )
    validate_unique_terminal_tool_event(
        conn=conn,
        conv_id=conv_id,
        assistant_at_ms=validated_timestamp,
        event_type=validated_event_type,
        payload_json=payload_json,
    )
    chronology_result = resolve_assistant_event_chronology(
        event_type=validated_event_type,
        payload_json=payload_json,
        running_visible_length=running_visible_length,
    )
    validated_payload_json = build_validated_assistant_event_payload_json(
        event_type=validated_event_type,
        payload_json=chronology_result.payload_json,
    )
    try:
        conn.execute(
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
            (
                conv_id,
                validated_timestamp,
                validated_sequence,
                validated_assistant_revision,
                validated_event_type,
                validated_payload_json,
                validated_created_at_ms,
            ),
        )
    except sqlite3.IntegrityError as exception:
        if is_terminal_tool_event_unique_integrity_error(exception):
            raise_duplicate_terminal_tool_event()
        raise
