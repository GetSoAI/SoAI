"""SoAI - Messaging provider outcome transitions [backend/database/repositories/users/messaging_delivery_outcomes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from database.repositories.users.messaging_delivery_receipts import (
    sync_apply_deferred_messaging_receipt,
)
from database.repositories.users.messaging_delivery_state_transitions import (
    DELIVERY_CLAIM_WHERE,
    MAX_CHUNK_ATTEMPTS,
    sync_requeue_claimed_messaging_attempt,
    sync_terminalize_claimed_messaging_delivery,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "sync_record_messaging_chunk_failure",
    "sync_record_messaging_chunk_sent",
)


def _record_interaction_prompt_identity(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    ordinal: int,
    provider_message_id: str,
) -> None:
    if ordinal != 0:
        return
    row = conn.execute(
        """
        SELECT route.route_id, route.provider_prompt_message_id
        FROM messaging_deliveries AS delivery
        JOIN messaging_interaction_routes AS route
          ON delivery.source_event_id = 'conversation_interaction_required:' || route.task_id
        WHERE delivery.delivery_id = ? AND delivery.purpose = 'interaction'
        LIMIT 1
        """,
        (delivery_id,),
    ).fetchone()
    if row is None:
        return
    if row[1] is not None and row[1] != provider_message_id:
        raise StateError("Messaging interaction prompt identity is already bound.")
    conn.execute(
        """
        UPDATE messaging_interaction_routes
        SET provider_prompt_message_id = ?
        WHERE route_id = ? AND provider_prompt_message_id IS NULL
        """,
        (provider_message_id, row[0]),
    )


def sync_record_messaging_chunk_sent(
    conn: sqlite3.Connection,
    delivery_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    ordinal: int,
    provider_message_id: str,
    next_request_delay_ms: int,
    now_ms: int,
) -> JSONDict:
    claim = conn.execute(
        f"SELECT account_id FROM messaging_deliveries AS delivery WHERE {DELIVERY_CLAIM_WHERE}",
        (delivery_id, claim_generation, claim_owner, server_boot_id),
    ).fetchone()
    if claim is None:
        return {"state": "stale"}
    updated = conn.execute(
        """
        UPDATE messaging_delivery_chunks
        SET state = 'sent', provider_message_id = ?, terminal_at_ms = ?, updated_at_ms = ?
        WHERE delivery_id = ? AND ordinal = ? AND state = 'sending'
          AND request_started_at_ms IS NOT NULL
        """,
        (provider_message_id, now_ms, now_ms, delivery_id, ordinal),
    ).rowcount
    if updated != 1:
        raise StateError("Messaging delivery chunk changed after provider success.")
    if not isinstance(claim[0], str) or not claim[0]:
        raise StateError("Messaging delivery account is invalid after provider success.")
    _record_interaction_prompt_identity(
        conn,
        delivery_id=delivery_id,
        ordinal=ordinal,
        provider_message_id=provider_message_id,
    )
    remaining = conn.execute(
        """
        SELECT COUNT(*) FROM messaging_delivery_chunks
        WHERE delivery_id = ? AND state != 'sent'
        """,
        (delivery_id,),
    ).fetchone()
    if remaining is None or not isinstance(remaining[0], int):
        raise StateError("Messaging delivery remaining chunk count is invalid.")
    if remaining[0] == 0:
        parent_updated = conn.execute(
            f"""
            UPDATE messaging_deliveries AS delivery
            SET state = 'sent', provider_message_id = ?, failure_code = NULL,
                claim_owner = NULL, claim_server_boot_id = NULL,
                terminal_at_ms = ?, updated_at_ms = ?
            WHERE {DELIVERY_CLAIM_WHERE}
            """,
            (
                provider_message_id,
                now_ms,
                now_ms,
                delivery_id,
                claim_generation,
                claim_owner,
                server_boot_id,
            ),
        ).rowcount
        state = "sent"
    else:
        parent_updated = conn.execute(
            f"""
            UPDATE messaging_deliveries AS delivery
            SET state = 'pending', failure_code = NULL, claim_owner = NULL,
                claim_server_boot_id = NULL, next_attempt_at_ms = ?, updated_at_ms = ?
            WHERE {DELIVERY_CLAIM_WHERE}
            """,
            (
                now_ms + max(next_request_delay_ms, 0),
                now_ms,
                delivery_id,
                claim_generation,
                claim_owner,
                server_boot_id,
            ),
        ).rowcount
        state = "pending"
    if parent_updated != 1:
        raise StateError("Messaging delivery parent changed after provider success.")
    sync_apply_deferred_messaging_receipt(
        conn,
        account_id=claim[0],
        provider_message_id=provider_message_id,
    )
    return {"state": state, "provider_message_id": provider_message_id}


def sync_record_messaging_chunk_failure(
    conn: sqlite3.Connection,
    delivery_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    ordinal: int,
    outcome: str,
    failure_code: str,
    retry_after_ms: int | None,
    now_ms: int,
) -> JSONDict:
    if outcome not in {"retryable", "failed", "delivery_unknown"}:
        raise ValidationError("Messaging delivery failure outcome is invalid.")
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
        return {"state": "stale"}
    if row[1] is None:
        raise StateError("Messaging provider outcome preceded request start.")
    if outcome == "retryable" and row[0] < MAX_CHUNK_ATTEMPTS:
        requeued = sync_requeue_claimed_messaging_attempt(
            conn,
            delivery_id=delivery_id,
            claim_generation=claim_generation,
            claim_owner=claim_owner,
            server_boot_id=server_boot_id,
            ordinal=ordinal,
            failure_code=failure_code,
            next_attempt_at_ms=now_ms + max(retry_after_ms or 0, 0),
            now_ms=now_ms,
        )
        return {"state": "pending" if requeued else "stale", "failure_code": failure_code}
    if outcome == "retryable":
        outcome = "failed"
        failure_code = "provider_retry_limit_exhausted"
    terminalized = sync_terminalize_claimed_messaging_delivery(
        conn,
        delivery_id=delivery_id,
        claim_generation=claim_generation,
        claim_owner=claim_owner,
        server_boot_id=server_boot_id,
        terminal_state=outcome,
        failure_code=failure_code,
        now_ms=now_ms,
        unknown_ordinal=ordinal if outcome == "delivery_unknown" else None,
    )
    if not terminalized:
        return {"state": "stale"}
    return {"delivery_id": delivery_id, "state": outcome, "failure_code": failure_code}
