"""SoAI - OpenAI Responses repository write operations [backend/database/repositories/openai_responses/write_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from database.core.storage_fields import require_storage_text
from database.repositories.openai_responses.ownership import (
    normalize_response_owner,
)
from database.repositories.openai_responses.write_ops_events import (
    sync_append_events,
    sync_delete_events,
)
from database.repositories.openai_responses.write_ops_input_items import (
    sync_replace_input_items,
)
from database.repositories.openai_responses.write_ops_response_rows import (
    sync_upsert_response,
)
from database.repositories.openai_responses.write_ops_shared import (
    read_existing_response_state,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_upsert_response_artifacts",)


def sync_upsert_response_artifacts(
    conn: sqlite3.Connection,
    response_id: str,
    task_id: str,
    user_id: int | None,
    api_key_id: str | None,
    model: str,
    created_at_ms: int,
    status: str,
    store: bool,
    is_background: bool,
    stream_enabled: bool,
    response_json: JSONDict,
    input_items: Sequence[JSONDict] | None,
    input_items_created_at_ms: int,
    event_payloads: Sequence[JSONDict],
    event_sequence_start: int,
    reset_events: bool,
    create_if_missing: bool,
    event_created_at_ms: int,
) -> bool:
    normalized_response_id = require_storage_text(response_id, field="response_id")
    owner = normalize_response_owner(user_id=user_id, api_key_id=api_key_id)
    existing_state = read_existing_response_state(conn, response_id=normalized_response_id)
    if existing_state is not None:
        if existing_state != owner:
            raise ValidationError("Response ownership mismatch.")
    elif not create_if_missing:
        return False
    sync_upsert_response(
        conn,
        response_id,
        task_id,
        user_id,
        api_key_id,
        model,
        created_at_ms,
        status,
        store,
        is_background,
        stream_enabled,
        response_json,
    )
    if input_items is not None:
        sync_replace_input_items(
            conn,
            response_id,
            input_items,
            input_items_created_at_ms,
        )
    if reset_events:
        sync_delete_events(
            conn,
            response_id,
        )
    if event_payloads:
        sync_append_events(
            conn,
            response_id,
            int(event_sequence_start),
            event_payloads,
            int(event_created_at_ms),
        )
    return True
