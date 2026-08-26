"""SoAI - OpenAI Responses repository write operation for status updates with event append [backend/database/repositories/openai_responses/write_ops_status_and_event.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from database.repositories.openai_responses.write_ops_events import sync_append_event
from database.repositories.openai_responses.write_ops_shared import (
    normalize_response_mutation_scope,
    read_next_response_event_sequence,
    sync_update_response_row_status,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_append_nonterminal_response_event",)


def sync_append_nonterminal_response_event(
    conn: sqlite3.Connection,
    response_id: str,
    response_json: JSONDict,
    event_json: JSONDict,
    event_created_at_ms: int,
    user_id: int | None = None,
    api_key_id: str | None = None,
) -> int | None:
    scope = normalize_response_mutation_scope(
        response_id,
        user_id=user_id,
        api_key_id=api_key_id,
    )
    updated = sync_update_response_row_status(
        conn,
        scope=scope,
        status="in_progress",
        response_json_text=serialize_json_compact_stable(response_json),
        allowed_statuses=("queued", "in_progress"),
    )
    if updated != 1:
        return None
    sequence = read_next_response_event_sequence(conn, response_id=scope.response_id)
    enriched_event = dict(event_json)
    enriched_event["sequence_number"] = sequence
    sync_append_event(
        conn,
        scope.response_id,
        sequence,
        enriched_event,
        int(event_created_at_ms),
    )
    return sequence
