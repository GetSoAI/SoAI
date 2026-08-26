"""SoAI - Tool call repository insert transactions [backend/database/repositories/users/tool_call_insert_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.database.requests import CreateToolCallRequest, CreateToolCallResult
from core.errors.exceptions import ValidationError
from core.timing.epoch import epoch_ms
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_errors import parse_sqlite_integrity_error
from database.repositories.users.context_compaction_metric_events import (
    sync_record_context_compaction_metric_event,
)
from database.repositories.users.tool_call_chronology_validation import (
    resolve_tool_call_content_anchor_against_assistant_message,
)
from database.repositories.users.tool_call_identity_queries import (
    build_tool_call_identity_query,
)
from database.repositories.users.tool_call_insert_conflicts import (
    resolve_tool_call_insert_conflict,
)
from database.repositories.users.tool_call_insert_identity import (
    ValidatedToolCallInsertFields,
    load_inserted_tool_call_result,
)
from database.repositories.users.tool_call_validation import (
    require_non_empty_string_from_row,
    resolve_tool_call_sequence_index,
    validate_collapsed_value,
    validate_non_negative_integer,
    validate_optional_epoch_ms_integer,
    validate_optional_string,
    validate_required_epoch_ms_integer,
    validate_status,
    validate_status_completed_at_ms_pair,
    validate_terminal_status_error_message,
)

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "select_tool_call_by_identity",
    "sync_create_tool_call",
)


def select_tool_call_by_identity(
    conn: sqlite3.Connection,
    *,
    conv_id: str,
    turn_id: str | None,
    iteration_index: int | None,
    message_index: int | None,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    call_id: str,
) -> SQLiteRowDict | None:
    query, query_params = build_tool_call_identity_query(
        conv_id=conv_id,
        call_id=call_id,
        turn_id=turn_id,
        iteration_index=iteration_index,
        message_index=message_index,
        assistant_turn_at_ms=assistant_turn_at_ms,
        model_variant_index=model_variant_index,
    )
    cursor = conn.execute(query, query_params)
    return sync_fetch_one_as_dict(cursor)


def sync_create_tool_call(
    conn: sqlite3.Connection,
    request: CreateToolCallRequest,
) -> CreateToolCallResult:
    validated_call_id = require_non_empty_string_from_row(request.call_id, "call_id")
    validated_conv_id = require_non_empty_string_from_row(request.conv_id, "conv_id")
    validated_tool_name = require_non_empty_string_from_row(request.tool_name, "tool_name")
    validated_turn_id = (
        request.turn_id.strip()
        if isinstance(request.turn_id, str) and request.turn_id.strip()
        else None
    )
    validated_iteration_index = validate_non_negative_integer(
        request.iteration_index,
        "iteration_index",
    )
    validated_status = validate_status(
        request.status,
        operation="create",
        call_id=validated_call_id,
    )
    created_candidate = epoch_ms() if request.created_at_ms is None else request.created_at_ms
    created_at_ms = validate_required_epoch_ms_integer(created_candidate, "created_at_ms")
    storage_call_id = (
        request.storage_call_id.strip()
        if isinstance(request.storage_call_id, str) and request.storage_call_id.strip()
        else validated_call_id
    )
    validated_message_index = validate_non_negative_integer(request.message_index, "message_index")
    validated_assistant_turn_at_ms = validate_required_epoch_ms_integer(
        request.assistant_turn_at_ms,
        "assistant_turn_at_ms",
    )
    validated_model_variant_index = validate_non_negative_integer(
        request.model_variant_index,
        "model_variant_index",
    )
    if validated_model_variant_index is None:
        raise ValidationError("Tool call field 'model_variant_index' is required.")
    validated_assistant_at_ms = validate_optional_epoch_ms_integer(
        request.assistant_at_ms,
        "assistant_at_ms",
    )
    validated_content_index_before = validate_non_negative_integer(
        request.content_index_before,
        "content_index_before",
    )
    if validated_content_index_before is None:
        raise ValidationError("Tool call field 'content_index_before' is required.")
    validated_thinking_index_before = validate_non_negative_integer(
        request.thinking_index_before,
        "thinking_index_before",
    )
    if validated_thinking_index_before is None:
        raise ValidationError("Tool call field 'thinking_index_before' is required.")
    validated_duration_ms = validate_non_negative_integer(request.duration_ms, "duration_ms")
    duration_ms = validated_duration_ms if validated_duration_ms is not None else 0
    validated_started_at_ms = validate_optional_epoch_ms_integer(
        request.started_at_ms,
        "started_at_ms",
    )
    validated_thinking_duration_before_ms = validate_non_negative_integer(
        request.thinking_duration_before_ms,
        "thinking_duration_before_ms",
    )
    validated_completed_at = validate_optional_epoch_ms_integer(
        request.completed_at_ms,
        "completed_at_ms",
    )
    validate_status_completed_at_ms_pair(
        validated_status,
        validated_completed_at,
        operation="create",
        call_id=validated_call_id,
    )
    validated_error_message = validate_optional_string(request.error_message, "error_message")
    validated_error_message = validate_terminal_status_error_message(
        validated_status,
        validated_error_message,
        operation="create",
        call_id=validated_call_id,
    )
    validated_owner_task_id = validate_optional_string(request.owner_task_id, "owner_task_id")
    if validated_owner_task_id is not None:
        validated_owner_task_id = validated_owner_task_id.strip()
        if not validated_owner_task_id:
            raise ValidationError("Tool call field 'owner_task_id' must not be empty.")
    sequence_index = resolve_tool_call_sequence_index(request.sequence_index)
    content_index_before = resolve_tool_call_content_anchor_against_assistant_message(
        conn,
        conv_id=validated_conv_id,
        assistant_turn_at_ms=validated_assistant_turn_at_ms,
        model_variant_index=validated_model_variant_index,
        content_index_before=validated_content_index_before,
    )
    collapsed_value = validate_collapsed_value(request.collapsed)
    fields = ValidatedToolCallInsertFields(
        storage_call_id=storage_call_id,
        call_id=validated_call_id,
        conv_id=validated_conv_id,
        turn_id=validated_turn_id,
        iteration_index=validated_iteration_index,
        message_index=validated_message_index,
        assistant_at_ms=validated_assistant_at_ms,
        assistant_turn_at_ms=validated_assistant_turn_at_ms,
        model_variant_index=validated_model_variant_index,
        tool_name=validated_tool_name,
        tool_arguments=request.tool_arguments,
        sequence_index=sequence_index,
        content_index_before=content_index_before,
        thinking_index_before=validated_thinking_index_before,
        thinking_duration_before_ms=validated_thinking_duration_before_ms,
    )
    try:
        conn.execute(
            """INSERT INTO webui_chat_tool_calls (
                id, call_id, conv_id, turn_id, iteration_index, message_index, assistant_at_ms,
                assistant_turn_at_ms, model_variant_index, tool_name, tool_arguments, tool_result, status,
                owner_task_id, error_message, duration_ms, sequence_index, content_index_before, thinking_index_before,
                thinking_duration_before_ms, collapsed, started_at_ms, created_at_ms, completed_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                storage_call_id,
                validated_call_id,
                validated_conv_id,
                validated_turn_id,
                validated_iteration_index,
                validated_message_index,
                validated_assistant_at_ms,
                validated_assistant_turn_at_ms,
                validated_model_variant_index,
                validated_tool_name,
                request.tool_arguments,
                request.tool_result,
                validated_status,
                validated_owner_task_id,
                validated_error_message,
                duration_ms,
                sequence_index,
                content_index_before,
                validated_thinking_index_before,
                validated_thinking_duration_before_ms,
                collapsed_value,
                validated_started_at_ms,
                created_at_ms,
                validated_completed_at,
            ),
        )
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        storage_conflict = _tool_call_storage_id_exists(conn, storage_call_id)
        if storage_conflict:
            return resolve_tool_call_insert_conflict(
                conn,
                request=request,
                fields=fields,
                status=validated_status,
                error_message=validated_error_message,
                duration_ms=duration_ms,
                started_at_ms=validated_started_at_ms,
                completed_at_ms=validated_completed_at,
            )
        message = "".join(
            (
                "Tool call persistence conflict ",
                f"({constraint_type}): {detail or 'unknown constraint'} ",
                f"(conv_id={validated_conv_id}, message_index={validated_message_index}, ",
                f"assistant_turn_at_ms={validated_assistant_turn_at_ms}, ",
                f"model_variant_index={validated_model_variant_index}, ",
                f"iteration_index={validated_iteration_index}, sequence_index={sequence_index}, ",
                f"call_id={validated_call_id}).",
            ),
        )
        raise ValidationError(message) from exception
    result = load_inserted_tool_call_result(conn, fields)
    sync_record_context_compaction_metric_event(conn, result.row)
    return result


def _tool_call_storage_id_exists(conn: sqlite3.Connection, storage_call_id: str) -> bool:
    cursor = conn.execute("SELECT 1 FROM webui_chat_tool_calls WHERE id = ?", (storage_call_id,))
    return sync_fetch_one_as_dict(cursor) is not None
