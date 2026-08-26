"""SoAI - Conversation draft row mapping [backend/database/repositories/users/conversation_draft_row_mapping.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.conversation_draft_content_validation import (
    validate_conversation_draft_entries,
)
from core.errors.exceptions import StateError
from core.serialization.json import serialize_json_compact_stable
from core.serialization.json_parsing import parse_json_value
from core.validation.epoch import EPOCH_MS_MIN
from database.core.sqlite_row_scalars import (
    require_sqlite_row_int,
    require_sqlite_row_non_empty_str,
    require_sqlite_row_str,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteRow

__all__ = (
    "format_conversation_draft_row",
    "parse_conversation_draft_attachment_json",
    "serialize_conversation_draft_entries",
)

CONVERSATION_DRAFT_ROW_FIELD_LABEL = "Conversation draft row field"


def parse_conversation_draft_attachment_json(raw: str) -> list[JSONValue]:
    parsed = parse_json_value(raw, field="conversation draft attachment_content_json")
    if not isinstance(parsed, list):
        raise StateError("Conversation draft attachment_content_json must be a JSON array.")
    return validate_conversation_draft_entries(parsed)


def serialize_conversation_draft_entries(entries: list[JSONValue]) -> str:
    return serialize_json_compact_stable(validate_conversation_draft_entries(entries))


def format_conversation_draft_row(
    row: SQLiteRow | None,
    *,
    attachment_content: list[JSONValue],
    attachments: list[JSONDict],
    dropped_attachment_count: int,
) -> JSONDict | None:
    if row is None:
        return None
    return {
        "conv_id": require_sqlite_row_non_empty_str(
            row,
            "conv_id",
            label=CONVERSATION_DRAFT_ROW_FIELD_LABEL,
        ),
        "user_id": require_sqlite_row_int(
            row,
            "user_id",
            label=CONVERSATION_DRAFT_ROW_FIELD_LABEL,
            minimum=1,
        ),
        "text": require_sqlite_row_str(row, "text", label=CONVERSATION_DRAFT_ROW_FIELD_LABEL),
        "source_text": require_sqlite_row_str(
            row,
            "source_text",
            label=CONVERSATION_DRAFT_ROW_FIELD_LABEL,
        ),
        "attachment_content": attachment_content,
        "attachments": attachments,
        "dropped_attachment_count": int(dropped_attachment_count),
        "created_at_ms": require_sqlite_row_int(
            row,
            "created_at_ms",
            label=CONVERSATION_DRAFT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
        "updated_at_ms": require_sqlite_row_int(
            row,
            "updated_at_ms",
            label=CONVERSATION_DRAFT_ROW_FIELD_LABEL,
            minimum=EPOCH_MS_MIN,
        ),
        "client_id": require_sqlite_row_non_empty_str(
            row,
            "client_id",
            label=CONVERSATION_DRAFT_ROW_FIELD_LABEL,
        ),
    }
