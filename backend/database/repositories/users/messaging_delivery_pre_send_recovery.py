"""SoAI - Messaging attempts proven unstarted before provider execution [backend/database/repositories/users/messaging_delivery_pre_send_recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from database.repositories.users.messaging_delivery_state_transitions import (
    DELIVERY_CLAIM_WHERE,
    MAX_CHUNK_ATTEMPTS,
    sync_requeue_claimed_messaging_attempt,
    sync_terminalize_claimed_messaging_delivery,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_record_messaging_claim_not_started",
    "sync_record_messaging_claim_pre_send_failure",
)


def _read_chunk_attempt(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    ordinal: int,
) -> tuple[int, int | None] | None:
    row = conn.execute(
        f"""
        SELECT chunk.attempt_count, chunk.request_started_at_ms
        FROM messaging_deliveries AS delivery
        JOIN messaging_delivery_chunks AS chunk
          ON chunk.delivery_id = delivery.delivery_id AND chunk.ordinal = ?
        WHERE {DELIVERY_CLAIM_WHERE} AND chunk.state = 'sending'
        """,
        (ordinal, delivery_id, claim_generation, claim_owner, server_boot_id),
    ).fetchone()
    if row is None:
        return None
    if not isinstance(row[0], int) or row[0] < 1:
        raise StateError("Messaging unstarted chunk attempt count is invalid.")
    if row[1] is not None and not isinstance(row[1], int):
        raise StateError("Messaging unstarted request marker is invalid.")
    return (row[0], row[1])


def sync_record_messaging_claim_pre_send_failure(
    conn: sqlite3.Connection,
    delivery_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    ordinal: int,
    failure_code: str,
    now_ms: int,
) -> JSONDict:
    attempt = _read_chunk_attempt(
        conn,
        delivery_id=delivery_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
        ordinal=ordinal,
    )
    if attempt is None:
        return {"state": "stale"}
    if attempt[1] is not None:
        raise StateError("Messaging pre-send failure followed a started provider request.")
    terminalized = sync_terminalize_claimed_messaging_delivery(
        conn,
        delivery_id=delivery_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
        terminal_state="failed",
        failure_code=failure_code,
        now_ms=now_ms,
    )
    return {
        "state": "failed" if terminalized else "stale",
        "failure_code": failure_code,
    }


def sync_record_messaging_claim_not_started(
    conn: sqlite3.Connection,
    delivery_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    ordinal: int,
    failure_code: str,
    retry_after_ms: int,
    now_ms: int,
) -> JSONDict:
    attempt = _read_chunk_attempt(
        conn,
        delivery_id=delivery_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
        ordinal=ordinal,
    )
    if attempt is None:
        return {"state": "stale"}
    if attempt[0] >= MAX_CHUNK_ATTEMPTS:
        terminalized = sync_terminalize_claimed_messaging_delivery(
            conn,
            delivery_id=delivery_id,
            claim_generation=claim_generation,
            claim_owner=claim_owner,
            server_boot_id=server_boot_id,
            terminal_state="failed",
            failure_code="delivery_pre_send_retry_limit_exhausted",
            now_ms=now_ms,
        )
        return {
            "state": "failed" if terminalized else "stale",
            "failure_code": "delivery_pre_send_retry_limit_exhausted",
        }
    requeued = sync_requeue_claimed_messaging_attempt(
        conn,
        delivery_id=delivery_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
        ordinal=ordinal,
        failure_code=failure_code,
        next_attempt_at_ms=now_ms + max(retry_after_ms, 0),
        now_ms=now_ms,
    )
    return {"state": "pending" if requeued else "stale", "failure_code": failure_code}
