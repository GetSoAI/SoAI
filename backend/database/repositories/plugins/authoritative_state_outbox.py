"""SoAI - Authoritative plugin state outbox sync operations [backend/database/repositories/plugins/authoritative_state_outbox.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError
from core.timing.epoch import epoch_ms
from core.timing.retry_backoff import compute_exponential_backoff_seconds
from database.repositories.outbox.status_writes import (
    sync_record_outbox_row_retryable_failure,
)

__all__ = (
    "compute_authoritative_state_retry_at",
    "sync_mark_authoritative_state_event_failed",
    "sync_mark_authoritative_state_event_published",
    "sync_record_authoritative_plugin_state_transition",
    "sync_record_authoritative_state_enqueue_failure",
    "sync_record_authoritative_state_processing_failure",
)

AUTHORITATIVE_STATE_RETRY_MAX_DELAY_SECONDS = 2_147_483.0


def sync_record_authoritative_plugin_state_transition(
    conn: sqlite3.Connection,
    plugin_name: str,
    new_state: str,
    event_id: str,
    event_type: str,
    payload_json: str,
    created_at_ms: int,
) -> int:
    updated = (
        conn.execute(
            """
            UPDATE plugins_catalog
            SET state = ?, last_seen_at_ms = ?
            WHERE plugin_name = ?
            """,
            (new_state, int(created_at_ms), plugin_name),
        ).rowcount
        > 0
    )
    if not updated:
        raise StateError(
            "Cannot record authoritative state transition for an unknown plugin.",
            operation="database.plugins.authoritative_state_outbox.record_transition",
            details={"plugin_name": plugin_name, "state": new_state},
        )
    cursor = conn.execute(
        """
        INSERT INTO plugin_authoritative_state_outbox (
            event_id,
            plugin_name,
            event_type,
            payload_json,
            created_at_ms,
            status,
            attempts,
            next_attempt_at_ms
        ) VALUES (?, ?, ?, ?, ?, 'pending', 0, 0)
        """,
        (
            event_id,
            plugin_name,
            event_type,
            payload_json,
            int(created_at_ms),
        ),
    )

    sequence = cursor.lastrowid
    if sequence is None or sequence <= 0:
        raise StateError("The authoritative state publication position is invalid.")
    return sequence


def sync_mark_authoritative_state_event_published(
    conn: sqlite3.Connection,
    outbox_id: int,
    published_at_ms: int,
) -> None:
    updated = (
        conn.execute(
            """
            UPDATE plugin_authoritative_state_outbox
            SET status = 'published', published_at_ms = ?, processing_started_at_ms = NULL
            WHERE id = ?
            """,
            (int(published_at_ms), int(outbox_id)),
        ).rowcount
        > 0
    )
    if not updated:
        raise StateError(
            "Failed to mark authoritative state outbox row as published.",
            operation="database.plugins.authoritative_state_outbox.mark_published",
            details={"outbox_id": outbox_id},
        )


def sync_record_authoritative_state_enqueue_failure(
    conn: sqlite3.Connection,
    outbox_id: int,
    attempts: int,
    next_attempt_at_ms: int,
    error_message: str,
) -> None:
    updated = sync_record_outbox_row_retryable_failure(
        conn,
        table="plugin_authoritative_state_outbox",
        outbox_id=outbox_id,
        attempts=attempts,
        next_attempt_at_ms=next_attempt_at_ms,
        error_message=error_message,
    )
    if not updated:
        raise StateError(
            "Failed to record authoritative state enqueue failure.",
            operation="database.plugins.authoritative_state_outbox.record_enqueue_failure",
            details={"outbox_id": outbox_id},
        )


def sync_record_authoritative_state_processing_failure(
    conn: sqlite3.Connection,
    outbox_id: int,
    attempts: int,
    error_message: str,
) -> None:
    updated = (
        conn.execute(
            """
            UPDATE plugin_authoritative_state_outbox
            SET
                status = 'processing',
                attempts = ?,
                last_error = ?
            WHERE id = ?
            """,
            (
                int(attempts),
                str(error_message or ""),
                int(outbox_id),
            ),
        ).rowcount
        > 0
    )
    if not updated:
        raise StateError(
            "Failed to record authoritative state processing failure.",
            operation="database.plugins.authoritative_state_outbox.record_processing_failure",
            details={"outbox_id": outbox_id},
        )


def sync_mark_authoritative_state_event_failed(
    conn: sqlite3.Connection,
    outbox_id: int,
    attempts: int,
    error_message: str,
) -> None:
    updated = (
        conn.execute(
            """
            UPDATE plugin_authoritative_state_outbox
            SET
                status = 'failed',
                attempts = ?,
                last_error = ?,
                processing_started_at_ms = NULL
            WHERE id = ?
            """,
            (
                int(attempts),
                str(error_message or ""),
                int(outbox_id),
            ),
        ).rowcount
        > 0
    )
    if not updated:
        raise StateError(
            "Failed to mark authoritative state outbox row as failed.",
            operation="database.plugins.authoritative_state_outbox.mark_failed",
            details={"outbox_id": outbox_id},
        )


def compute_authoritative_state_retry_at(*, attempts: int, base_delay_ms: int) -> int:
    bounded_attempts = max(1, min(int(attempts), 8))
    delay_ms = int(
        compute_exponential_backoff_seconds(
            bounded_attempts - 1,
            base_seconds=float(max(250, int(base_delay_ms))) / 1000.0,
            maximum_seconds=AUTHORITATIVE_STATE_RETRY_MAX_DELAY_SECONDS,
        )
        * 1000.0,
    )
    return epoch_ms() + delay_ms
