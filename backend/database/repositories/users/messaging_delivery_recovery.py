"""SoAI - Interrupted Messaging delivery reconciliation [backend/database/repositories/users/messaging_delivery_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from database.repositories.users.messaging_delivery_state_transitions import (
    DELIVERY_CLAIM_WHERE,
    sync_terminalize_messaging_delivery,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_reconcile_prior_boot_messaging_deliveries",
    "sync_settle_messaging_delivery_worker_failure",
)


def _finalize_all_sent_delivery(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    now_ms: int,
) -> None:
    row = conn.execute(
        """
        SELECT provider_message_id FROM messaging_delivery_chunks
        WHERE delivery_id = ? ORDER BY ordinal DESC LIMIT 1
        """,
        (delivery_id,),
    ).fetchone()
    if row is None or not isinstance(row[0], str) or not row[0]:
        raise StateError("Recovered Messaging delivery has no final provider identity.")
    updated = conn.execute(
        """
        UPDATE messaging_deliveries
        SET state = 'sent', provider_message_id = ?, failure_code = NULL,
            claim_owner = NULL, claim_server_boot_id = NULL,
            terminal_at_ms = ?, updated_at_ms = ?
        WHERE delivery_id = ? AND state = 'sending'
        """,
        (row[0], now_ms, now_ms, delivery_id),
    ).rowcount
    if updated != 1:
        raise StateError("Recovered Messaging delivery lost its parent state.")


def _reconcile_delivery(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    now_ms: int,
    unknown_failure_code: str,
    retry_failure_code: str,
) -> str:
    rows = conn.execute(
        """
        SELECT ordinal, state, request_started_at_ms
        FROM messaging_delivery_chunks
        WHERE delivery_id = ? ORDER BY ordinal
        """,
        (delivery_id,),
    ).fetchall()
    if not rows:
        sync_terminalize_messaging_delivery(
            conn,
            delivery_id=delivery_id,
            expected_state="sending",
            terminal_state="failed",
            failure_code="messaging_delivery_chunks_missing",
            now_ms=now_ms,
        )
        return "failed"
    sending = tuple(row for row in rows if row[1] == "sending")
    marked = tuple(row for row in sending if row[2] is not None)
    if marked:
        unknown_ordinal = min(int(row[0]) for row in marked)
        sync_terminalize_messaging_delivery(
            conn,
            delivery_id=delivery_id,
            expected_state="sending",
            terminal_state="delivery_unknown",
            failure_code=unknown_failure_code,
            now_ms=now_ms,
            unknown_ordinal=unknown_ordinal,
        )
        return "delivery_unknown"
    if sending:
        conn.execute(
            """
            UPDATE messaging_delivery_chunks
            SET state = 'pending', request_started_at_ms = NULL, updated_at_ms = ?
            WHERE delivery_id = ? AND state = 'sending'
            """,
            (now_ms, delivery_id),
        )
    states = tuple("pending" if row[1] == "sending" else str(row[1]) for row in rows)
    if all(state == "sent" for state in states):
        _finalize_all_sent_delivery(conn, delivery_id=delivery_id, now_ms=now_ms)
        return "sent"
    if "delivery_unknown" in states:
        sync_terminalize_messaging_delivery(
            conn,
            delivery_id=delivery_id,
            expected_state="sending",
            terminal_state="delivery_unknown",
            failure_code=unknown_failure_code,
            now_ms=now_ms,
        )
        return "delivery_unknown"
    if "failed" in states:
        sync_terminalize_messaging_delivery(
            conn,
            delivery_id=delivery_id,
            expected_state="sending",
            terminal_state="failed",
            failure_code="interrupted_delivery_failed",
            now_ms=now_ms,
        )
        return "failed"
    updated = conn.execute(
        """
        UPDATE messaging_deliveries
        SET state = 'pending', claim_owner = NULL, claim_server_boot_id = NULL,
            failure_code = ?, next_attempt_at_ms = ?, updated_at_ms = ?
        WHERE delivery_id = ? AND state = 'sending'
        """,
        (retry_failure_code, now_ms, now_ms, delivery_id),
    ).rowcount
    if updated != 1:
        raise StateError("Interrupted Messaging delivery lost its parent state.")
    return "pending"


def sync_reconcile_prior_boot_messaging_deliveries(
    conn: sqlite3.Connection,
    current_server_boot_id: str,
    recovered_at_ms: int,
) -> int:
    rows = conn.execute(
        """
        SELECT delivery_id FROM messaging_deliveries
        WHERE state = 'sending' AND claim_server_boot_id != ?
        ORDER BY created_at_ms, delivery_id
        """,
        (current_server_boot_id,),
    ).fetchall()
    for row in rows:
        _reconcile_delivery(
            conn,
            delivery_id=str(row[0]),
            now_ms=recovered_at_ms,
            unknown_failure_code="interrupted_delivery_unknown",
            retry_failure_code="interrupted_before_delivery",
        )
    return len(rows)


def sync_settle_messaging_delivery_worker_failure(
    conn: sqlite3.Connection,
    delivery_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    settled_at_ms: int,
) -> JSONDict:
    row = conn.execute(
        f"SELECT 1 FROM messaging_deliveries AS delivery WHERE {DELIVERY_CLAIM_WHERE}",
        (delivery_id, claim_generation, claim_owner, server_boot_id),
    ).fetchone()
    if row is None:
        return {"state": "stale"}
    state = _reconcile_delivery(
        conn,
        delivery_id=delivery_id,
        now_ms=settled_at_ms,
        unknown_failure_code="delivery_worker_failed_unknown",
        retry_failure_code="delivery_worker_failed_before_request",
    )
    return {"state": state}
