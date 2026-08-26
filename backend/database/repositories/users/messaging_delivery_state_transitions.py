"""SoAI - Atomic Messaging parent and chunk state transitions [backend/database/repositories/users/messaging_delivery_state_transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError

__all__ = (
    "DELIVERY_CLAIM_WHERE",
    "MAX_CHUNK_ATTEMPTS",
    "sync_requeue_claimed_messaging_attempt",
    "sync_terminalize_claimed_messaging_delivery",
    "sync_terminalize_messaging_delivery",
)

DELIVERY_CLAIM_WHERE = (
    "delivery.delivery_id = ? AND delivery.state = 'sending' "
    "AND delivery.claim_generation = ? AND delivery.claim_owner = ? "
    "AND delivery.claim_server_boot_id = ?"
)
MAX_CHUNK_ATTEMPTS = 5


def _terminalize_unsent_chunks(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    unknown_ordinal: int | None,
    now_ms: int,
) -> None:
    conn.execute(
        """
        UPDATE messaging_delivery_chunks
        SET state = CASE WHEN ordinal = ? THEN 'delivery_unknown' ELSE 'failed' END,
            terminal_at_ms = ?, updated_at_ms = ?
        WHERE delivery_id = ? AND state IN ('pending', 'sending')
        """,
        (unknown_ordinal, now_ms, now_ms, delivery_id),
    )


def sync_terminalize_messaging_delivery(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    expected_state: str,
    terminal_state: str,
    failure_code: str,
    now_ms: int,
    unknown_ordinal: int | None = None,
) -> bool:
    updated = conn.execute(
        """
        UPDATE messaging_deliveries
        SET state = ?, failure_code = ?, claim_owner = NULL,
            claim_server_boot_id = NULL, terminal_at_ms = ?, updated_at_ms = ?
        WHERE delivery_id = ? AND state = ?
        """,
        (
            terminal_state,
            failure_code,
            now_ms,
            now_ms,
            delivery_id,
            expected_state,
        ),
    ).rowcount
    if updated == 0:
        return False
    if updated != 1:
        raise StateError("Messaging delivery terminal transition affected invalid rows.")
    _terminalize_unsent_chunks(
        conn,
        delivery_id=delivery_id,
        unknown_ordinal=unknown_ordinal,
        now_ms=now_ms,
    )
    return True


def sync_terminalize_claimed_messaging_delivery(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    terminal_state: str,
    failure_code: str,
    now_ms: int,
    unknown_ordinal: int | None = None,
) -> bool:
    updated = conn.execute(
        f"""
        UPDATE messaging_deliveries AS delivery
        SET state = ?, failure_code = ?, claim_owner = NULL,
            claim_server_boot_id = NULL, terminal_at_ms = ?, updated_at_ms = ?
        WHERE {DELIVERY_CLAIM_WHERE}
        """,
        (
            terminal_state,
            failure_code,
            now_ms,
            now_ms,
            delivery_id,
            claim_generation,
            claim_owner,
            server_boot_id,
        ),
    ).rowcount
    if updated == 0:
        return False
    if updated != 1:
        raise StateError("Messaging claimed terminal transition affected invalid rows.")
    _terminalize_unsent_chunks(
        conn,
        delivery_id=delivery_id,
        unknown_ordinal=unknown_ordinal,
        now_ms=now_ms,
    )
    return True


def sync_requeue_claimed_messaging_attempt(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    ordinal: int,
    failure_code: str,
    next_attempt_at_ms: int,
    now_ms: int,
) -> bool:
    claim = conn.execute(
        f"SELECT 1 FROM messaging_deliveries AS delivery WHERE {DELIVERY_CLAIM_WHERE}",
        (delivery_id, claim_generation, claim_owner, server_boot_id),
    ).fetchone()
    if claim is None:
        return False
    chunk_updated = conn.execute(
        """
        UPDATE messaging_delivery_chunks
        SET state = 'pending', request_started_at_ms = NULL, updated_at_ms = ?
        WHERE delivery_id = ? AND ordinal = ? AND state = 'sending'
        """,
        (now_ms, delivery_id, ordinal),
    ).rowcount
    if chunk_updated != 1:
        raise StateError("Messaging delivery requeue lost its selected chunk.")
    parent_updated = conn.execute(
        f"""
        UPDATE messaging_deliveries AS delivery
        SET state = 'pending', failure_code = ?, claim_owner = NULL,
            claim_server_boot_id = NULL, next_attempt_at_ms = ?, updated_at_ms = ?
        WHERE {DELIVERY_CLAIM_WHERE}
        """,
        (
            failure_code,
            next_attempt_at_ms,
            now_ms,
            delivery_id,
            claim_generation,
            claim_owner,
            server_boot_id,
        ),
    ).rowcount
    if parent_updated != 1:
        raise StateError("Messaging delivery requeue lost its parent claim.")
    return True
