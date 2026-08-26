"""SoAI - Tool call live event read operations [backend/database/repositories/users/tool_call_live_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.serialization.json import normalize_for_json
from core.tool_calls.live_event_paging import resolve_tool_call_live_event_page_limit
from core.types.json_value import coerce_json_dict
from core.validation.strict_numbers import require_positive_int_strict
from database.core.flags import FEATURE_PROMPTS
from database.core.json_codec import safe_json_deserialize
from database.core.query_execution import query_to_dicts
from database.repositories.users.conversation_query_filters import (
    conversation_exists_for_user,
)
from database.repositories.users.tool_call_validation import (
    require_non_empty_string_from_row,
    require_non_negative_integer_from_row,
    require_optional_non_negative_integer_from_row,
    validate_required_epoch_ms_integer,
    validate_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRow
    from database.repositories.users.internal_protocols import (
        DatabaseMessagesCoreOwnerProtocol,
    )

__all__ = ("get_tool_call_live_events_page",)


def _format_live_event_row(row: SQLiteRow) -> JSONDict:
    conv_id = require_non_empty_string_from_row(row.get("conv_id"), "conv_id")
    call_id = require_non_empty_string_from_row(row.get("call_id"), "call_id")
    event_type = require_non_empty_string_from_row(row.get("event_type"), "event_type")
    assistant_turn_at_ms = validate_required_epoch_ms_integer(
        require_non_negative_integer_from_row(
            row.get("assistant_turn_at_ms"),
            "assistant_turn_at_ms",
        ),
        "assistant_turn_at_ms",
    )
    assistant_at_ms = validate_required_epoch_ms_integer(
        require_non_negative_integer_from_row(row.get("assistant_at_ms"), "assistant_at_ms"),
        "assistant_at_ms",
    )
    model_variant_index = require_non_negative_integer_from_row(
        row.get("model_variant_index"),
        "model_variant_index",
    )
    live_sequence = require_non_negative_integer_from_row(row.get("live_sequence"), "live_sequence")
    created_at_ms = validate_required_epoch_ms_integer(
        require_non_negative_integer_from_row(row.get("created_at_ms"), "created_at_ms"),
        "created_at_ms",
    )
    duration_ms = require_optional_non_negative_integer_from_row(
        row.get("duration_ms"),
        "duration_ms",
    )
    projection_revision = require_positive_int_strict(
        row.get("projection_revision"),
        error_message="Tool call live event projection_revision must be a positive integer.",
    )
    status = require_non_empty_string_from_row(row.get("status"), "status")
    validate_status(status, operation="read live event", call_id=call_id)
    payload_raw = safe_json_deserialize(row.get("payload_json"), None)
    if not isinstance(payload_raw, dict):
        raise ValidationError("Tool call live event payload_json must decode to an object.")
    payload = coerce_json_dict(normalize_for_json(payload_raw))
    if payload is None:
        raise ValidationError("Tool call live event payload_json is invalid.")
    return {
        "conv_id": conv_id,
        "assistant_turn_at_ms": assistant_turn_at_ms,
        "model_variant_index": model_variant_index,
        "assistant_at_ms": assistant_at_ms,
        "call_id": call_id,
        "live_sequence": live_sequence,
        "event_type": event_type,
        "payload": payload,
        "created_at_ms": created_at_ms,
        "duration_ms": duration_ms,
        "status": status,
        "projection_revision": projection_revision,
    }


async def get_tool_call_live_events_page(
    self: DatabaseMessagesCoreOwnerProtocol,
    *,
    conv_id: str,
    user_id: int,
    assistant_turn_at_ms: int,
    model_variant_index: int,
    call_id: str,
    before_live_sequence: int | None,
    limit: int,
) -> JSONDict | None:
    self.core.features.ensure_feature_enabled(FEATURE_PROMPTS)
    page_limit = resolve_tool_call_live_event_page_limit(limit)
    validated_before: int | None = None
    if before_live_sequence is not None:
        validated_before = require_optional_non_negative_integer_from_row(
            before_live_sequence,
            "before_live_sequence",
        )

    async def _query(database: aiosqlite.Connection) -> JSONDict | None:
        if not await conversation_exists_for_user(database, conv_id=conv_id, user_id=user_id):
            return None
        if validated_before is None:
            rows = await query_to_dicts(
                database,
                """
                SELECT *
                FROM webui_tool_call_live_events
                WHERE conv_id = ?
                  AND assistant_turn_at_ms = ?
                  AND model_variant_index = ?
                  AND call_id = ?
                ORDER BY live_sequence DESC
                LIMIT ?
                """,
                (conv_id, assistant_turn_at_ms, model_variant_index, call_id, page_limit),
            )
        else:
            rows = await query_to_dicts(
                database,
                """
                SELECT *
                FROM webui_tool_call_live_events
                WHERE conv_id = ?
                  AND assistant_turn_at_ms = ?
                  AND model_variant_index = ?
                  AND call_id = ?
                  AND live_sequence < ?
                ORDER BY live_sequence DESC
                LIMIT ?
                """,
                (
                    conv_id,
                    assistant_turn_at_ms,
                    model_variant_index,
                    call_id,
                    validated_before,
                    page_limit,
                ),
            )
        events = [_format_live_event_row(row) for row in rows]
        next_before = None
        if len(events) == page_limit:
            last_event = events[-1]
            candidate = last_event.get("live_sequence")
            next_before = candidate if isinstance(candidate, int) and candidate > 0 else None
        return {"events": events, "next_before_live_sequence": next_before}

    return await self.core.reader.execute_read(_query)
