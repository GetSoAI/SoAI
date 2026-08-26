"""SoAI - Tool call live event repository transactions [backend/database/repositories/users/tool_call_live_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.database.requests import RecordToolCallLiveEventRequest
from core.errors.exceptions import StateError, ValidationError
from core.tool_calls.status_values import (
    is_active_tool_call_status,
    resolve_tool_call_status_rank,
)
from database.core.query_execution import sync_fetch_one_as_dict
from database.repositories.users.assistant_tool_event_payload_validation import (
    build_validated_live_tool_event_payload_json,
)
from database.repositories.users.context_compaction_metric_events import (
    sync_record_context_compaction_metric_event,
)
from database.repositories.users.tool_call_live_chronology import (
    validate_live_projection_chronology,
)
from database.repositories.users.tool_call_row_mapping import format_tool_call_row
from database.repositories.users.tool_call_validation import (
    require_non_empty_string_from_row,
    validate_non_negative_integer,
    validate_required_epoch_ms_integer,
    validate_status,
    validate_tool_call_write_fields,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("sync_record_tool_call_live_event",)


def _load_projection_row(
    conn: sqlite3.Connection,
    request: RecordToolCallLiveEventRequest,
) -> SQLiteRowDict:
    cursor = conn.execute(
        """
        SELECT *
        FROM webui_chat_tool_calls
        WHERE conv_id = ?
          AND assistant_turn_at_ms = ?
          AND model_variant_index = ?
          AND call_id = ?
        ORDER BY created_at_ms DESC, id DESC
        LIMIT 1
        """,
        (
            request.conv_id,
            request.assistant_turn_at_ms,
            request.model_variant_index,
            request.call_id,
        ),
    )
    row = sync_fetch_one_as_dict(cursor)
    if row is None:
        raise StateError("Tool live event projection row was not found.")
    return row


def _allocate_live_sequence(
    conn: sqlite3.Connection,
    request: RecordToolCallLiveEventRequest,
) -> int:
    cursor = conn.execute(
        """
        SELECT COALESCE(MAX(live_sequence) + 1, 0) AS next_sequence
        FROM webui_tool_call_live_events
        WHERE conv_id = ?
          AND assistant_turn_at_ms = ?
          AND model_variant_index = ?
          AND call_id = ?
        """,
        (
            request.conv_id,
            request.assistant_turn_at_ms,
            request.model_variant_index,
            request.call_id,
        ),
    )
    row = sync_fetch_one_as_dict(cursor)
    if row is None:
        raise StateError("Tool live event sequence allocation failed.")
    next_sequence = validate_non_negative_integer(row.get("next_sequence"), "live_sequence")
    if next_sequence is None:
        raise StateError("Tool live event sequence allocation returned no sequence.")
    return next_sequence


def _resolve_projection_revision(row: SQLiteRowDict) -> int:
    current_revision = validate_non_negative_integer(row.get("live_revision"), "live_revision")
    if current_revision is None:
        current_revision = 0
    return current_revision + 1


def _validate_formatted_live_projection(
    formatted: JSONDict,
    *,
    live_sequence: int,
    projection_revision: int,
    last_live_event_at_ms: int,
) -> None:
    if formatted.get("live_revision") != projection_revision:
        raise StateError("Tool live event projection revision did not advance.")
    if formatted.get("last_live_sequence") != live_sequence:
        raise StateError("Tool live event projection sequence did not advance.")
    if formatted.get("last_live_event_at_ms") != last_live_event_at_ms:
        raise StateError("Tool live event timestamp did not advance.")


def sync_record_tool_call_live_event(
    conn: sqlite3.Connection,
    request: RecordToolCallLiveEventRequest,
) -> JSONDict:
    validated_conv_id = require_non_empty_string_from_row(request.conv_id, "conv_id")
    validated_call_id = require_non_empty_string_from_row(request.call_id, "call_id")
    validated_event_type = require_non_empty_string_from_row(request.event_type, "event_type")
    validated_assistant_turn_at_ms = validate_required_epoch_ms_integer(
        request.assistant_turn_at_ms,
        "assistant_turn_at_ms",
    )
    validated_assistant_at_ms = validate_required_epoch_ms_integer(
        request.assistant_at_ms,
        "assistant_at_ms",
    )
    validated_model_variant_index = validate_non_negative_integer(
        request.model_variant_index,
        "model_variant_index",
    )
    if validated_model_variant_index is None:
        raise ValidationError("Tool live event model_variant_index is required.")
    validated_created_at_ms = validate_required_epoch_ms_integer(
        request.created_at_ms,
        "created_at_ms",
    )
    validated_fields = validate_tool_call_write_fields(
        status=request.status,
        error_message=request.error_message,
        duration_ms=request.duration_ms,
        started_at_ms=request.started_at_ms,
        completed_at_ms=request.completed_at_ms,
        operation="live update",
        call_id=validated_call_id,
    )
    if validated_fields.status is None:
        raise ValidationError("Tool live event status is required.")
    projection_row = _load_projection_row(conn, request)
    validate_live_projection_chronology(
        conn=conn,
        request=request,
        projection_row=projection_row,
        conv_id=validated_conv_id,
        assistant_turn_at_ms=validated_assistant_turn_at_ms,
        model_variant_index=validated_model_variant_index,
    )
    validated_payload_json = build_validated_live_tool_event_payload_json(request.payload_json)
    projection_id = require_non_empty_string_from_row(projection_row.get("id"), "id")
    current_status = require_non_empty_string_from_row(projection_row.get("status"), "status")
    current_status = validate_status(
        current_status,
        operation="live projection update",
        call_id=validated_call_id,
    )
    current_status_is_active = is_active_tool_call_status(current_status)
    apply_projection_update = current_status_is_active and resolve_tool_call_status_rank(
        validated_fields.status,
    ) >= resolve_tool_call_status_rank(current_status)
    projected_status = validated_fields.status if apply_projection_update else current_status
    live_sequence = _allocate_live_sequence(conn, request)
    projection_revision = _resolve_projection_revision(projection_row)
    conn.execute(
        """
        INSERT INTO webui_tool_call_live_events (
            conv_id, assistant_turn_at_ms, model_variant_index, call_id, live_sequence,
            assistant_at_ms, event_type, payload_json, created_at_ms, duration_ms, status,
            projection_revision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            validated_conv_id,
            validated_assistant_turn_at_ms,
            validated_model_variant_index,
            validated_call_id,
            live_sequence,
            validated_assistant_at_ms,
            validated_event_type,
            validated_payload_json,
            validated_created_at_ms,
            validated_fields.duration_ms,
            validated_fields.status,
            projection_revision,
        ),
    )
    cursor = conn.execute(
        """
        UPDATE webui_chat_tool_calls
        SET
            status = CASE
                WHEN ? AND status IN ('pending', 'running') THEN ?
                ELSE status
            END,
            tool_result = CASE
                WHEN ? AND status IN ('pending', 'running') THEN COALESCE(?, tool_result)
                ELSE tool_result
            END,
            error_message = CASE
                WHEN ? AND status IN ('pending', 'running') THEN COALESCE(?, error_message)
                ELSE error_message
            END,
            duration_ms = CASE
                WHEN ? AND status IN ('pending', 'running') THEN COALESCE(?, duration_ms, 0)
                ELSE duration_ms
            END,
            started_at_ms = CASE
                WHEN ? AND status IN ('pending', 'running') THEN COALESCE(?, started_at_ms)
                ELSE started_at_ms
            END,
            completed_at_ms = CASE
                WHEN ? AND status IN ('pending', 'running') THEN COALESCE(?, completed_at_ms)
                ELSE completed_at_ms
            END,
            live_revision = ?,
            last_live_event_at_ms = ?,
            last_live_sequence = ?
        WHERE id = ?
        """,
        (
            apply_projection_update,
            projected_status,
            apply_projection_update,
            request.tool_result,
            apply_projection_update,
            validated_fields.error_message,
            apply_projection_update,
            validated_fields.duration_ms,
            apply_projection_update,
            validated_fields.started_at_ms,
            apply_projection_update,
            validated_fields.completed_at_ms,
            projection_revision,
            validated_created_at_ms,
            live_sequence,
            projection_id,
        ),
    )
    if cursor.rowcount != 1:
        raise StateError("Tool live event projection metadata update failed.")
    cursor = conn.execute(
        "SELECT * FROM webui_chat_tool_calls WHERE id = ?",
        (projection_id,),
    )
    formatted = format_tool_call_row(sync_fetch_one_as_dict(cursor))
    if formatted is None:
        raise StateError("Tool live event projection row could not be loaded after update.")
    _validate_formatted_live_projection(
        formatted,
        live_sequence=live_sequence,
        projection_revision=projection_revision,
        last_live_event_at_ms=validated_created_at_ms,
    )
    sync_record_context_compaction_metric_event(conn, formatted)
    formatted["live_sequence"] = live_sequence
    formatted["live_event_type"] = validated_event_type
    return formatted
