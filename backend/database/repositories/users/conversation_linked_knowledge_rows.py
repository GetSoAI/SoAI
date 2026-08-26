"""SoAI - Linked knowledge row formatting [backend/database/repositories/users/conversation_linked_knowledge_rows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

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

__all__ = (
    "format_linked_knowledge_item_row",
    "format_linked_knowledge_link_row",
)

LINKED_KNOWLEDGE_ROW_FIELD_LABEL = "Linked knowledge row field"


def format_linked_knowledge_item_row(row: SQLiteRow) -> JSONDict:
    return {
        "source_conv_id": require_sqlite_row_non_empty_str(
            row,
            "source_conv_id",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
        "source_user_id": require_sqlite_row_int(
            row,
            "source_user_id",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
            minimum=1,
        ),
        "source_knowledge_attachment_id": require_sqlite_row_non_empty_str(
            row,
            "source_knowledge_attachment_id",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
        "source_item_id": require_sqlite_row_int(
            row,
            "source_item_id",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
            minimum=1,
        ),
        "source_document_id": require_sqlite_row_non_empty_str(
            row,
            "source_document_id",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
        "filename": require_sqlite_row_non_empty_str(
            row,
            "filename",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
        "file_type": require_sqlite_row_non_empty_str(
            row,
            "file_type",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
        "file_size_bytes": require_sqlite_row_int(
            row,
            "file_size_bytes",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
        "document_status": require_sqlite_row_non_empty_str(
            row,
            "document_status",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
        "item_rag_status": sqlite_row_optional_str(
            row,
            "item_rag_status",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
        "document_created_at_ms": require_sqlite_row_int(
            row,
            "document_created_at_ms",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
        "chunk_count": sqlite_row_optional_int(
            row,
            "chunk_count",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
    }


def format_linked_knowledge_link_row(row: SQLiteRow) -> JSONDict:
    return {
        "source_conv_id": require_sqlite_row_non_empty_str(
            row,
            "source_conv_id",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
        "source_user_id": require_sqlite_row_int(
            row,
            "source_user_id",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
            minimum=1,
        ),
        "source_knowledge_attachment_id": require_sqlite_row_non_empty_str(
            row,
            "source_knowledge_attachment_id",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
        "source_item_id": require_sqlite_row_int(
            row,
            "source_item_id",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
            minimum=1,
        ),
        "source_document_id": require_sqlite_row_non_empty_str(
            row,
            "source_document_id",
            label=LINKED_KNOWLEDGE_ROW_FIELD_LABEL,
        ),
    }
