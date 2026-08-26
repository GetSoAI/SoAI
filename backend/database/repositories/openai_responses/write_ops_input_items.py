"""SoAI - OpenAI Responses repository write operations for input items [backend/database/repositories/openai_responses/write_ops_input_items.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable
from core.validation.strings import coerce_optional_trimmed_str
from database.core.storage_fields import require_storage_text

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_replace_input_items",)


def sync_replace_input_items(
    conn: sqlite3.Connection,
    response_id: str,
    items: Sequence[JSONDict],
    created_at_ms: int,
) -> None:
    normalized_response_id = require_storage_text(response_id, field="response_id")
    conn.execute(
        "DELETE FROM openai_response_input_items WHERE response_id = ?",
        (normalized_response_id,),
    )
    for index, item in enumerate(items):
        item_id = coerce_optional_trimmed_str(item.get("id"))
        if item_id is None:
            raise ValidationError("Input item is missing required id.")
        payload_text = serialize_json_compact_stable(item)
        conn.execute(
            """
            INSERT INTO openai_response_input_items (
                response_id,
                item_index,
                item_id,
                item_json,
                created_at_ms
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                normalized_response_id,
                int(index),
                item_id,
                payload_text,
                int(created_at_ms),
            ),
        )
