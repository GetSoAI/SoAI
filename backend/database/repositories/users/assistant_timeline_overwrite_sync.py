"""SoAI - Assistant timeline overwrite synchronization [backend/database/repositories/users/assistant_timeline_overwrite_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.assistant_timeline.event_timeline_validation import (
    validate_assistant_event_timeline,
)
from core.conversations.conversation_message_storage_types import (
    ConversationMessageStoragePayload,
)
from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.validation.record_fields import require_json_object, require_json_object_list
from database.repositories.users.assistant_event_field_validation import (
    validate_assistant_event_assistant_revision,
    validate_assistant_event_epoch_timestamp,
    validate_assistant_event_sequence,
    validate_assistant_event_type,
)
from database.repositories.users.assistant_tool_event_payload_validation import (
    build_validated_timeline_event_payload,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_assistant_timelines_from_messages",)


def _sync_assistant_event_rows(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
    timeline: list[JSONDict],
    created_at_ms: int,
) -> None:
    validated_assistant_at_ms = validate_assistant_event_epoch_timestamp(
        assistant_at_ms,
        field_name="assistant_at_ms",
    )
    validated_created_at_ms = validate_assistant_event_epoch_timestamp(
        created_at_ms,
        field_name="created_at_ms",
    )
    conn.execute(
        "DELETE FROM webui_assistant_message_events WHERE conv_id = ? AND assistant_at_ms = ?",
        (conv_id, validated_assistant_at_ms),
    )
    if not timeline:
        return
    rows: list[tuple[str, int, int, int, str, str, int]] = []
    for event in timeline:
        sequence = validate_assistant_event_sequence(event.get("sequence"))
        assistant_revision = validate_assistant_event_assistant_revision(
            event.get("assistant_revision"),
        )
        event_type = validate_assistant_event_type(event.get("event_type"))
        payload = require_json_object(
            event.get("payload"),
            label="Assistant event timeline payload",
            build_error=ValidationError,
            invalid_message="Assistant event timeline payload is invalid.",
        )
        sanitized_payload_json = build_validated_timeline_event_payload(
            event_type=event_type,
            payload=payload,
        )
        rows.append(
            (
                conv_id,
                validated_assistant_at_ms,
                sequence,
                assistant_revision,
                event_type,
                serialize_json_compact_stable_strict(sanitized_payload_json),
                validated_created_at_ms,
            ),
        )
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
        rows,
    )


def _sync_assistant_tool_call_rows_to_timeline(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
    completed_call_ids: set[str],
) -> None:
    if not completed_call_ids:
        conn.execute(
            "DELETE FROM webui_tool_call_live_events WHERE conv_id = ? AND assistant_at_ms = ?",
            (conv_id, assistant_at_ms),
        )
        conn.execute(
            "DELETE FROM webui_chat_tool_calls WHERE conv_id = ? AND assistant_at_ms = ?",
            (conv_id, assistant_at_ms),
        )
        return
    placeholders = ",".join("?" for _ in completed_call_ids)
    conn.execute(
        f"DELETE FROM webui_tool_call_live_events WHERE conv_id = ? AND assistant_at_ms = ? AND call_id NOT IN ({placeholders})",
        (conv_id, assistant_at_ms, *sorted(completed_call_ids)),
    )
    conn.execute(
        f"DELETE FROM webui_chat_tool_calls WHERE conv_id = ? AND assistant_at_ms = ? AND call_id NOT IN ({placeholders})",
        (conv_id, assistant_at_ms, *sorted(completed_call_ids)),
    )


def sync_assistant_timelines_from_messages(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    validated_messages: list[ConversationMessageStoragePayload],
    created_at_ms: int,
) -> None:
    for message_index, validated in enumerate(validated_messages):
        if validated.get("role") != "assistant":
            continue
        assistant_at_ms = validated.get("created_at_ms")
        timeline = validated.get("assistant_event_timeline")
        if not isinstance(assistant_at_ms, int) or not isinstance(timeline, list):
            raise ValidationError("Assistant message timeline persistence state is invalid.")
        completed_call_ids = validate_assistant_event_timeline(
            timeline,
            message_index=message_index,
            assistant_at_ms=assistant_at_ms,
        )
        normalized_timeline = require_json_object_list(
            timeline,
            label="Assistant message timeline",
            build_error=ValidationError,
            invalid_message="Assistant message timeline persistence state is invalid.",
            entry_message="Assistant message timeline persistence state is invalid.",
        )
        _sync_assistant_event_rows(
            conn,
            conv_id=conv_id,
            assistant_at_ms=assistant_at_ms,
            timeline=normalized_timeline,
            created_at_ms=created_at_ms,
        )
        _sync_assistant_tool_call_rows_to_timeline(
            conn,
            conv_id=conv_id,
            assistant_at_ms=assistant_at_ms,
            completed_call_ids=completed_call_ids,
        )
