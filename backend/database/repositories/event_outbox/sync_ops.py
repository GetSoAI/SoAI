"""SoAI - Domain event outbox sync operations (transactional outbox) [backend/database/repositories/event_outbox/sync_ops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.serialization.json import serialize_json_compact_stable_strict
from core.validation.integers import is_strict_int
from database.core.query_execution import sync_fetch_all_as_json_dicts
from database.repositories.outbox.status_writes import (
    sync_record_outbox_row_retryable_failure,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_claim_pending_domain_events",
    "sync_enqueue_domain_event",
    "sync_enqueue_domain_event_payload",
    "sync_ensure_domain_event_payload",
    "sync_mark_domain_event_failed_permanently",
    "sync_mark_domain_event_published",
    "sync_quarantine_domain_event_outbox_row",
    "sync_record_domain_event_failure",
)


def sync_enqueue_domain_event(
    conn: sqlite3.Connection,
    event_id: str,
    event_type: str,
    payload_json: str,
    created_at_ms: int,
) -> None:
    invalid_event_identity = (
        not isinstance(event_id, str)
        or not event_id.strip()
        or not isinstance(event_type, str)
        or not event_type.strip()
    )
    invalid_payload = not isinstance(payload_json, str) or not payload_json
    invalid_timestamp = not is_strict_int(created_at_ms) or created_at_ms < 0
    if invalid_event_identity or invalid_payload or invalid_timestamp:
        raise StateError("Domain event outbox enqueue received invalid inputs.")
    conn.execute(
        """
        INSERT INTO webui_domain_event_outbox (
            event_id,
            event_type,
            payload_json,
            created_at_ms,
            status,
            attempts,
            next_attempt_at_ms
        ) VALUES (?, ?, ?, ?, 'pending', 0, 0)
        """,
        (event_id.strip(), event_type.strip(), payload_json, int(created_at_ms)),
    )


def sync_enqueue_domain_event_payload(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    payload: JSONDict,
    created_at_ms: int,
) -> None:
    if not isinstance(payload, dict):
        raise StateError("Domain event payload must be a JSON object.")
    raw_event_id = payload.get("event_id")
    if not isinstance(raw_event_id, str) or not raw_event_id:
        raise StateError("Domain event payload is missing a valid event_id.")
    sync_enqueue_domain_event(
        conn,
        event_id=raw_event_id,
        event_type=event_type,
        payload_json=serialize_json_compact_stable_strict(payload),
        created_at_ms=created_at_ms,
    )


def sync_ensure_domain_event_payload(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    payload: JSONDict,
    created_at_ms: int,
) -> None:
    raw_event_id = payload.get("event_id")
    if not isinstance(raw_event_id, str) or not raw_event_id:
        raise StateError("Domain event payload is missing a valid event_id.")
    payload_json = serialize_json_compact_stable_strict(payload)
    existing = conn.execute(
        "SELECT event_type, payload_json FROM webui_domain_event_outbox WHERE event_id = ?",
        (raw_event_id,),
    ).fetchone()
    if existing is not None:
        if existing[0] != event_type or existing[1] != payload_json:
            raise StateError("Domain event outbox identity collided.")
        return
    sync_enqueue_domain_event(
        conn,
        event_id=raw_event_id,
        event_type=event_type,
        payload_json=payload_json,
        created_at_ms=created_at_ms,
    )


def sync_claim_pending_domain_events(
    conn: sqlite3.Connection,
    now_ms: int,
    limit: int,
    processing_timeout_ms: int,
) -> list[JSONDict]:
    batch_limit = max(int(limit) or 1, 1)
    timeout_ms = max(int(processing_timeout_ms) or 1, 1)
    now_value = int(now_ms)
    expired_processing_before = now_value - timeout_ms
    cursor = conn.execute(
        """
        SELECT id, event_id, event_type, payload_json, attempts
        FROM webui_domain_event_outbox
        WHERE
            (
                status = 'pending'
                AND next_attempt_at_ms <= ?
            )
            OR (
                status = 'processing'
                AND processing_started_at_ms IS NOT NULL
                AND processing_started_at_ms <= ?
            )
        ORDER BY id
        LIMIT ?
        """,
        (now_value, expired_processing_before, batch_limit),
    )
    events = sync_fetch_all_as_json_dicts(cursor)
    if not events:
        return []
    ids: list[int] = []
    for event in events:
        raw_id = event.get("id")
        if not isinstance(raw_id, int):
            raise StateError("Domain event outbox contained invalid row id(s).")
        ids.append(int(raw_id))
    placeholders = ", ".join("?" for _ in ids)
    conn.execute(
        f"""
        UPDATE webui_domain_event_outbox
        SET status = 'processing', processing_started_at_ms = ?
        WHERE id IN ({placeholders})
        """,
        (now_value, *ids),
    )
    return events


def sync_mark_domain_event_published(
    conn: sqlite3.Connection,
    outbox_id: int,
    published_at_ms: int,
) -> None:
    updated = (
        conn.execute(
            """
            UPDATE webui_domain_event_outbox
            SET status = 'published', published_at_ms = ?, processing_started_at_ms = NULL
            WHERE id = ?
            """,
            (int(published_at_ms), int(outbox_id)),
        ).rowcount
        > 0
    )
    if not updated:
        raise StateError("Failed to mark domain outbox event as published.")


def sync_record_domain_event_failure(
    conn: sqlite3.Connection,
    outbox_id: int,
    attempts: int,
    next_attempt_at_ms: int,
    error_message: str,
) -> None:
    updated = sync_record_outbox_row_retryable_failure(
        conn,
        table="webui_domain_event_outbox",
        outbox_id=outbox_id,
        attempts=attempts,
        next_attempt_at_ms=next_attempt_at_ms,
        error_message=error_message,
    )
    if not updated:
        raise StateError("Failed to record domain outbox event failure.")


def sync_mark_domain_event_failed_permanently(
    conn: sqlite3.Connection,
    outbox_id: int,
    attempts: int,
    error_message: str,
) -> None:
    updated = (
        conn.execute(
            """
            UPDATE webui_domain_event_outbox
            SET
                status = 'failed',
                attempts = ?,
                last_error = ?,
                processing_started_at_ms = NULL
            WHERE id = ?
            """,
            (int(attempts), str(error_message or ""), int(outbox_id)),
        ).rowcount
        > 0
    )
    if not updated:
        raise StateError("Failed to mark domain outbox event as failed.")


def sync_quarantine_domain_event_outbox_row(
    conn: sqlite3.Connection,
    outbox_id: int,
    attempts: int,
    next_attempt_at_ms: int,
    error_message: str,
) -> None:
    updated = sync_record_outbox_row_retryable_failure(
        conn,
        table="webui_domain_event_outbox",
        outbox_id=outbox_id,
        attempts=attempts,
        next_attempt_at_ms=next_attempt_at_ms,
        error_message=error_message,
    )
    if not updated:
        raise StateError("Failed to quarantine domain outbox event.")
