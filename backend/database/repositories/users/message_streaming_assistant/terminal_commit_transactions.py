"""SoAI - Atomic streaming assistant terminal transactions [backend/database/repositories/users/message_streaming_assistant/terminal_commit_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.conversations.conversation_message_write_result import ConversationMessageWriteResult
from core.conversations.streaming_assistant_terminal_commit import (
    StreamingAssistantTerminalCommitRequest,
)
from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from database.repositories.users.assistant_event_chronology_validation import (
    resolve_assistant_event_chronology,
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
from database.repositories.users.conversation_ownership import ensure_conversation_owned
from database.repositories.users.conversation_versioning import (
    sync_load_conversation_last_modified_at_ms,
)
from database.repositories.users.message_count_sync import sync_count_stored_messages
from database.repositories.users.message_streaming_assistant.event_transactions import (
    sync_append_streaming_assistant_events_batch,
)
from database.repositories.users.message_streaming_assistant.message_finalization_transactions import (
    sync_finalize_streaming_assistant_message,
    sync_terminalize_input_with_assistant,
)
from database.repositories.users.message_streaming_assistant.message_transactions import (
    sync_update_streaming_assistant_content,
)
from database.repositories.users.message_streaming_assistant.terminal_event_normalization import (
    build_terminal_assistant_event_payload_json,
)

__all__ = ("sync_commit_streaming_assistant_terminal",)

_TERMINAL_EVENT_TYPES = frozenset(("completed", "cancelled", "error"))


def _resolve_visible_length_before_sequence(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    assistant_at_ms: int,
    sequence: int,
) -> int:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(LENGTH(COALESCE(json_extract(payload_json, '$.delta'), ''))), 0)
        FROM webui_assistant_message_events
        WHERE conv_id = ?
          AND assistant_at_ms = ?
          AND sequence < ?
          AND event_type = 'assistant_text_delta'
        """,
        (conv_id, assistant_at_ms, sequence),
    ).fetchone()
    value = row[0] if row is not None else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError("Persisted assistant visible length is invalid.")
    return int(value)


def _normalize_requested_events(
    conn: sqlite3.Connection,
    *,
    request: StreamingAssistantTerminalCommitRequest,
    serialized_events: tuple[tuple[int, int, str, str, int], ...],
    terminal_normalization_at_ms: int | None,
) -> tuple[tuple[tuple[int, int, str, str, int], ...], ...]:
    if not serialized_events:
        raise ValidationError("Streaming assistant terminal commit requires terminal events.")
    validated_events: list[tuple[int, int, str, str, int]] = []
    previous_sequence: int | None = None
    for sequence, revision, event_type, payload_json, created_at_ms in serialized_events:
        validated_sequence = validate_assistant_event_sequence(sequence)
        validated_revision = validate_assistant_event_assistant_revision(revision)
        validated_event_type = validate_assistant_event_type(event_type)
        validated_created_at_ms = validate_assistant_event_epoch_timestamp(
            created_at_ms,
            field_name="created_at_ms",
        )
        if validated_revision != validated_sequence + 1:
            raise ValidationError("Assistant event assistant_revision must equal sequence + 1.")
        if previous_sequence is not None and validated_sequence != previous_sequence + 1:
            raise ValidationError("Assistant event sequence must be contiguous.")
        if not isinstance(payload_json, str) or not payload_json.strip():
            raise ValidationError("Assistant event payload_json must be a non-empty JSON string.")
        validated_events.append(
            (
                validated_sequence,
                validated_revision,
                validated_event_type,
                payload_json,
                validated_created_at_ms,
            ),
        )
        previous_sequence = validated_sequence
    terminal_event_type = validated_events[-1][2]
    if terminal_event_type not in _TERMINAL_EVENT_TYPES:
        raise ValidationError(
            "Streaming assistant terminal commit requires a terminal final event."
        )
    if any(event[2] in _TERMINAL_EVENT_TYPES for event in validated_events[:-1]):
        raise ValidationError("Streaming assistant terminal event must be final in its batch.")
    terminal_finish_reason_matches = (
        (terminal_event_type == "error" and request.finalization.finish_reason == "error")
        or (
            terminal_event_type == "cancelled" and request.finalization.finish_reason == "cancelled"
        )
        or (
            terminal_event_type == "completed"
            and request.finalization.finish_reason not in {"error", "cancelled"}
        )
    )
    if not terminal_finish_reason_matches:
        raise ValidationError("Streaming assistant terminal event conflicts with finish reason.")
    visible_length = _resolve_visible_length_before_sequence(
        conn,
        conv_id=request.conv_id,
        assistant_at_ms=request.assistant_at_ms,
        sequence=validated_events[0][0],
    )
    terminal_created_at_ms = (
        validated_events[-1][4]
        if terminal_normalization_at_ms is None
        else terminal_normalization_at_ms
    )
    normalized: list[tuple[int, int, str, str, int]] = []
    for sequence, revision, event_type, payload_json, created_at_ms in validated_events:
        chronology = resolve_assistant_event_chronology(
            event_type=event_type,
            payload_json=payload_json,
            running_visible_length=visible_length,
        )
        validated_payload_json = build_validated_assistant_event_payload_json(
            event_type=event_type,
            payload_json=chronology.payload_json,
        )
        terminal_payload_json = build_terminal_assistant_event_payload_json(
            event_type=event_type,
            payload_json=validated_payload_json,
            finish_reason=request.finalization.finish_reason,
            terminal_reason=request.finalization.terminal_reason,
            now_ms=terminal_created_at_ms,
        )
        normalized.append(
            (sequence, revision, event_type, terminal_payload_json, created_at_ms),
        )
        visible_length = chronology.running_visible_length
    return tuple(validated_events), tuple(normalized)


def _validate_persisted_requested_events(
    conn: sqlite3.Connection,
    *,
    request: StreamingAssistantTerminalCommitRequest,
    normalized_events: tuple[tuple[int, int, str, str, int], ...],
) -> None:
    for sequence, revision, event_type, payload_json, _created_at_ms in normalized_events:
        row = conn.execute(
            """
            SELECT assistant_revision, event_type, payload_json
            FROM webui_assistant_message_events
            WHERE conv_id = ? AND assistant_at_ms = ? AND sequence = ?
            """,
            (request.conv_id, request.assistant_at_ms, sequence),
        ).fetchone()
        if row is None:
            raise ValidationError("Committed assistant terminal event sequence is missing.")
        if row[0] != revision or row[1] != event_type or row[2] != payload_json:
            raise ValidationError(
                "Committed assistant terminal event identity conflicts with retry."
            )


def _matching_finalized_assistant_exists(
    conn: sqlite3.Connection,
    request: StreamingAssistantTerminalCommitRequest,
) -> bool:
    row = conn.execute(
        """
        SELECT content, request_id, finish_reason, prompt_tokens, completion_tokens, total_tokens,
               usage_source, generation_latency_ms, thinking_tail_duration_ms, finalized_at_ms
        FROM webui_messages
        WHERE conv_id = ? AND created_at_ms = ? AND role = 'assistant'
        """,
        (request.conv_id, request.assistant_at_ms),
    ).fetchone()
    if row is None or row[9] is None:
        return False
    expected = (
        request.finalization.finish_reason,
        request.finalization.prompt_tokens,
        request.finalization.completion_tokens,
        request.finalization.total_tokens,
        request.finalization.usage_source,
        request.finalization.generation_latency_ms,
        request.finalization.thinking_tail_duration_ms,
    )
    content_conflicts = row[0] != serialize_json_compact_stable_strict(request.content_text)
    request_id_conflicts = request.request_id is not None and row[1] != request.request_id
    if content_conflicts or request_id_conflicts or tuple(row[2:9]) != expected:
        raise ValidationError("Finalized streaming assistant conflicts with terminal retry.")
    return True


def _resolve_persisted_terminal_created_at_ms(
    conn: sqlite3.Connection,
    *,
    request: StreamingAssistantTerminalCommitRequest,
) -> int:
    row = conn.execute(
        """
        SELECT created_at_ms
        FROM webui_assistant_message_events
        WHERE conv_id = ? AND assistant_at_ms = ?
        ORDER BY sequence DESC
        LIMIT 1
        """,
        (request.conv_id, request.assistant_at_ms),
    ).fetchone()
    if row is None:
        raise ValidationError("Committed assistant terminal event is missing.")
    return validate_assistant_event_epoch_timestamp(
        row[0],
        field_name="created_at_ms",
    )


def sync_commit_streaming_assistant_terminal(
    conn: sqlite3.Connection,
    request: StreamingAssistantTerminalCommitRequest,
    serialized_events: tuple[tuple[int, int, str, str, int], ...],
) -> ConversationMessageWriteResult:
    ensure_conversation_owned(conn, request.conv_id, request.user_id)
    validate_assistant_event_epoch_timestamp(
        request.assistant_at_ms,
        field_name="assistant_at_ms",
    )
    finalized_assistant_exists = _matching_finalized_assistant_exists(conn, request)
    terminal_normalization_at_ms = (
        _resolve_persisted_terminal_created_at_ms(conn, request=request)
        if finalized_assistant_exists
        else None
    )
    validated_events, normalized_events = _normalize_requested_events(
        conn,
        request=request,
        serialized_events=serialized_events,
        terminal_normalization_at_ms=terminal_normalization_at_ms,
    )
    if finalized_assistant_exists:
        _validate_persisted_requested_events(
            conn,
            request=request,
            normalized_events=normalized_events,
        )
        if request.input_finalization is not None:
            sync_terminalize_input_with_assistant(
                conn,
                conv_id=request.conv_id,
                created_at_ms=request.assistant_at_ms,
                finish_reason=request.finalization.finish_reason,
                terminal_code=request.finalization.terminal_code,
                input_finalization=request.input_finalization,
            )
        return ConversationMessageWriteResult(
            last_modified_at_ms=sync_load_conversation_last_modified_at_ms(
                conn,
                request.conv_id,
            ),
            message_count=sync_count_stored_messages(conn, request.conv_id),
        )
    expected_sequence = resolve_next_assistant_event_sequence(
        conn,
        conv_id=request.conv_id,
        assistant_at_ms=request.assistant_at_ms,
    )
    persisted_prefix = tuple(event for event in validated_events if event[0] < expected_sequence)
    if persisted_prefix:
        _validate_persisted_requested_events(
            conn,
            request=request,
            normalized_events=persisted_prefix,
        )
    sync_update_streaming_assistant_content(
        conn,
        request.conv_id,
        request.user_id,
        request.assistant_at_ms,
        request.content_text,
    )
    sync_append_streaming_assistant_events_batch(
        conn,
        request.conv_id,
        request.user_id,
        request.assistant_at_ms,
        list(normalized_events),
    )
    return sync_finalize_streaming_assistant_message(
        conn,
        request.conv_id,
        request.user_id,
        request.assistant_at_ms,
        request.request_id,
        request.finalization.finish_reason,
        request.finalization.prompt_tokens,
        request.finalization.completion_tokens,
        request.finalization.total_tokens,
        request.finalization.usage_source,
        request.finalization.generation_latency_ms,
        request.finalization.thinking_tail_duration_ms,
        request.finalization.terminal_reason,
        request.input_finalization,
        request.finalization.terminal_code,
    )
