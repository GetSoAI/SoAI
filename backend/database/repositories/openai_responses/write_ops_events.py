"""SoAI - OpenAI Responses event row write operations [backend/database/repositories/openai_responses/write_ops_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.serialization.json import serialize_json_compact_stable
from database.core.storage_fields import require_storage_text

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_append_event",
    "sync_append_events",
    "sync_delete_events",
)


def sync_append_event(
    conn: sqlite3.Connection,
    response_id: str,
    sequence: int,
    event_json: JSONDict,
    created_at_ms: int,
) -> None:
    normalized_response_id = require_storage_text(response_id, field="response_id")
    payload_text = serialize_json_compact_stable(event_json)
    conn.execute(
        """
        INSERT INTO openai_response_events (
            response_id,
            sequence,
            event_json,
            created_at_ms
        ) VALUES (?, ?, ?, ?)
        """,
        (
            normalized_response_id,
            int(sequence),
            payload_text,
            int(created_at_ms),
        ),
    )


def sync_append_events(
    conn: sqlite3.Connection,
    response_id: str,
    sequence_start: int,
    event_payloads: Sequence[JSONDict],
    created_at_ms: int,
) -> None:
    normalized_response_id = require_storage_text(response_id, field="response_id")
    sequence = int(sequence_start)
    params: list[tuple[str, int, str, int]] = []
    for event_json in event_payloads:
        if not isinstance(event_json, dict):
            continue
        payload_text = serialize_json_compact_stable(event_json)
        params.append(
            (
                normalized_response_id,
                int(sequence),
                payload_text,
                int(created_at_ms),
            ),
        )
        sequence += 1
    if not params:
        return
    conn.executemany(
        """
        INSERT INTO openai_response_events (
            response_id,
            sequence,
            event_json,
            created_at_ms
        ) VALUES (?, ?, ?, ?)
        """,
        params,
    )


def sync_delete_events(
    conn: sqlite3.Connection,
    response_id: str,
) -> None:
    normalized_response_id = require_storage_text(response_id, field="response_id")
    conn.execute(
        "DELETE FROM openai_response_events WHERE response_id = ?",
        (normalized_response_id,),
    )
