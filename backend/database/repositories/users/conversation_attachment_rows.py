"""SoAI - Conversation attachment row mapping [backend/database/repositories/users/conversation_attachment_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.serialization.json_parsing import parse_json_dict
from core.validation.epoch import EPOCH_MS_MIN
from database.core.sqlite_row_scalars import (
    require_sqlite_row_int,
    require_sqlite_row_non_empty_str,
    sqlite_row_optional_bool_from_int,
    sqlite_row_optional_int,
    sqlite_row_optional_str,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRow

__all__ = (
    "format_attachment_row",
    "format_knowledge_attachment_row",
)

ATTACHMENT_ROW_FIELD_LABEL = "Attachment row field"


def _status_counts(row: SQLiteRow) -> JSONDict:
    raw = row.get("status_counts_json")
    if raw is None:
        raise StateError("Knowledge attachment status_counts_json is missing.")
    if not isinstance(raw, str | bytes):
        raise StateError("Knowledge attachment status_counts_json is invalid.")
    return parse_json_dict(raw, field="status_counts_json")


def format_attachment_row(row: SQLiteRow | None) -> JSONDict | None:
    if row is None:
        return None
    payload: JSONDict = {
        "attachment_id": require_sqlite_row_non_empty_str(
            row,
            "id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "client_attachment_id": require_sqlite_row_non_empty_str(
            row,
            "client_attachment_id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "conv_id": require_sqlite_row_non_empty_str(
            row,
            "conv_id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "user_id": require_sqlite_row_int(
            row,
            "user_id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=1,
        ),
        "file_id": require_sqlite_row_non_empty_str(
            row,
            "file_id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "filename": require_sqlite_row_non_empty_str(
            row,
            "filename",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "mime_type": require_sqlite_row_non_empty_str(
            row,
            "mime_type",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "size_bytes": require_sqlite_row_int(row, "size_bytes", label=ATTACHMENT_ROW_FIELD_LABEL),
        "preview_type": require_sqlite_row_non_empty_str(
            row,
            "preview_type",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "provider_mode": sqlite_row_optional_str(
            row,
            "provider_mode",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "provider_text": sqlite_row_optional_str(
            row,
            "provider_text",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "provider_text_truncated": sqlite_row_optional_bool_from_int(
            row,
            "provider_text_truncated",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "parse_state": require_sqlite_row_non_empty_str(
            row,
            "parse_state",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "parse_error": sqlite_row_optional_str(
            row,
            "parse_error",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "parsed_at_ms": sqlite_row_optional_int(
            row,
            "parsed_at_ms",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
        "state": require_sqlite_row_non_empty_str(row, "state", label=ATTACHMENT_ROW_FIELD_LABEL),
        "conversation_input_id": sqlite_row_optional_str(
            row,
            "conversation_input_id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "message_created_at_ms": sqlite_row_optional_int(
            row,
            "message_created_at_ms",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
        "attachment_revision": require_sqlite_row_int(
            row,
            "attachment_revision",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "created_at_ms": require_sqlite_row_int(
            row,
            "created_at_ms",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
        "updated_at_ms": require_sqlite_row_int(
            row,
            "updated_at_ms",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
        "expires_at_ms": require_sqlite_row_int(
            row,
            "expires_at_ms",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
    }
    return payload


def format_knowledge_attachment_row(row: SQLiteRow | None) -> JSONDict | None:
    if row is None:
        return None
    payload: JSONDict = {
        "knowledge_attachment_id": require_sqlite_row_non_empty_str(
            row,
            "id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "summary_id": require_sqlite_row_non_empty_str(row, "id", label=ATTACHMENT_ROW_FIELD_LABEL),
        "conv_id": require_sqlite_row_non_empty_str(
            row,
            "conv_id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "user_id": require_sqlite_row_int(
            row,
            "user_id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=1,
        ),
        "state": require_sqlite_row_non_empty_str(row, "state", label=ATTACHMENT_ROW_FIELD_LABEL),
        "conversation_input_id": sqlite_row_optional_str(
            row,
            "conversation_input_id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "message_created_at_ms": sqlite_row_optional_int(
            row,
            "message_created_at_ms",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
        "processing_state": require_sqlite_row_non_empty_str(
            row,
            "processing_state",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "source_type": require_sqlite_row_non_empty_str(
            row,
            "source_type",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "operation_type": require_sqlite_row_non_empty_str(
            row,
            "operation_type",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "title": require_sqlite_row_non_empty_str(row, "title", label=ATTACHMENT_ROW_FIELD_LABEL),
        "root_label": sqlite_row_optional_str(row, "root_label", label=ATTACHMENT_ROW_FIELD_LABEL),
        "root_virtual_path": sqlite_row_optional_str(
            row,
            "root_virtual_path",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "task_id": sqlite_row_optional_str(row, "task_id", label=ATTACHMENT_ROW_FIELD_LABEL),
        "client_batch_id": sqlite_row_optional_str(
            row,
            "client_batch_id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "first_event_id": sqlite_row_optional_int(
            row,
            "first_event_id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "last_event_id": sqlite_row_optional_int(
            row,
            "last_event_id",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "state_signature": sqlite_row_optional_str(
            row,
            "state_signature",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "total_count": require_sqlite_row_int(row, "total_count", label=ATTACHMENT_ROW_FIELD_LABEL),
        "visible_count": require_sqlite_row_int(
            row,
            "visible_count",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "hidden_count": require_sqlite_row_int(
            row,
            "hidden_count",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "status_counts": _status_counts(row),
        "attachment_revision": require_sqlite_row_int(
            row,
            "attachment_revision",
            label=ATTACHMENT_ROW_FIELD_LABEL,
        ),
        "created_at_ms": require_sqlite_row_int(
            row,
            "created_at_ms",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
        "updated_at_ms": require_sqlite_row_int(
            row,
            "updated_at_ms",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
        "finalized_at_ms": sqlite_row_optional_int(
            row,
            "finalized_at_ms",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
        "expires_at_ms": require_sqlite_row_int(
            row,
            "expires_at_ms",
            label=ATTACHMENT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
    }
    return payload
