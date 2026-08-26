"""SoAI - Conversation attachment item row mapping [backend/database/repositories/users/conversation_attachment_item_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.types.json_value import coerce_json_dict
from core.validation.epoch import EPOCH_MS_MIN
from database.core.sqlite_row_scalars import (
    require_sqlite_row_int,
    require_sqlite_row_non_empty_str,
    sqlite_row_optional_int,
    sqlite_row_optional_str,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRow

__all__ = ("format_knowledge_attachment_item_row",)

ATTACHMENT_ITEM_ROW_FIELD_LABEL = "Attachment row field"


def format_knowledge_attachment_item_row(row: SQLiteRow) -> JSONDict:
    payload: JSONDict = {
        "id": require_sqlite_row_int(row, "id", label=ATTACHMENT_ITEM_ROW_FIELD_LABEL, minimum=1),
        "knowledge_attachment_id": require_sqlite_row_non_empty_str(
            row,
            "knowledge_attachment_id",
            label=ATTACHMENT_ITEM_ROW_FIELD_LABEL,
        ),
        "document_id": sqlite_row_optional_str(
            row,
            "document_id",
            label=ATTACHMENT_ITEM_ROW_FIELD_LABEL,
        ),
        "event_id": sqlite_row_optional_int(row, "event_id", label=ATTACHMENT_ITEM_ROW_FIELD_LABEL),
        "item_index": require_sqlite_row_int(
            row,
            "item_index",
            label=ATTACHMENT_ITEM_ROW_FIELD_LABEL,
        ),
        "filename": require_sqlite_row_non_empty_str(
            row,
            "filename",
            label=ATTACHMENT_ITEM_ROW_FIELD_LABEL,
        ),
        "file_type": sqlite_row_optional_str(
            row, "file_type", label=ATTACHMENT_ITEM_ROW_FIELD_LABEL
        ),
        "file_size_bytes": sqlite_row_optional_int(
            row,
            "file_size_bytes",
            label=ATTACHMENT_ITEM_ROW_FIELD_LABEL,
        ),
        "rag_status": sqlite_row_optional_str(
            row,
            "rag_status",
            label=ATTACHMENT_ITEM_ROW_FIELD_LABEL,
        ),
        "operation_type": require_sqlite_row_non_empty_str(
            row,
            "operation_type",
            label=ATTACHMENT_ITEM_ROW_FIELD_LABEL,
        ),
        "error_message": sqlite_row_optional_str(
            row,
            "error_message",
            label=ATTACHMENT_ITEM_ROW_FIELD_LABEL,
        ),
        "created_at_ms": require_sqlite_row_int(
            row,
            "created_at_ms",
            label=ATTACHMENT_ITEM_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
    }
    normalized = coerce_json_dict(payload)
    if normalized is None:
        raise StateError("Knowledge attachment item row is invalid.")
    return normalized
