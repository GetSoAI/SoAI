"""SoAI - Messaging provider receipt persistence [backend/database/repositories/users/messaging_delivery_receipts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.messaging.ingress_models import normalize_messaging_receipt_status

if TYPE_CHECKING:
    from core.messaging.ingress_models import MessagingReceiptStatus

__all__ = (
    "sync_apply_deferred_messaging_receipt",
    "sync_record_messaging_delivery_receipt",
)

_RECEIPT_STATES = frozenset(("sent", "delivered", "read", "failed"))


def _update_chunk_receipt(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    provider_message_id: str,
    receipt_status: MessagingReceiptStatus,
    receipt_at_ms: int,
) -> bool:
    row = conn.execute(
        """
        SELECT receipt_state, receipt_at_ms
        FROM messaging_delivery_chunks
        WHERE delivery_id = ? AND provider_message_id = ? AND state = 'sent'
        """,
        (delivery_id, provider_message_id),
    ).fetchone()
    if row is None:
        return False
    current_state, current_at_ms = row
    if current_state in {"read", "failed"}:
        return False
    if isinstance(current_at_ms, int) and receipt_at_ms < current_at_ms:
        return False
    if current_state == "delivered" and receipt_status == "sent":
        return False
    updated = conn.execute(
        """
        UPDATE messaging_delivery_chunks
        SET receipt_state = ?, receipt_at_ms = ?, updated_at_ms = MAX(updated_at_ms, ?)
        WHERE delivery_id = ? AND provider_message_id = ? AND state = 'sent'
          AND receipt_state IS ? AND receipt_at_ms IS ?
        """,
        (
            receipt_status,
            receipt_at_ms,
            receipt_at_ms,
            delivery_id,
            provider_message_id,
            current_state,
            current_at_ms,
        ),
    ).rowcount
    if updated != 1:
        raise StateError("Messaging provider receipt changed during update.")
    return True


def _project_delivery_receipt(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    receipt_at_ms: int,
) -> None:
    rows = conn.execute(
        """
        SELECT receipt_state FROM messaging_delivery_chunks
        WHERE delivery_id = ? ORDER BY ordinal
        """,
        (delivery_id,),
    ).fetchall()
    states = tuple(row[0] for row in rows)
    if not states:
        raise StateError("Messaging delivery receipt has no chunks.")
    if "failed" in states:
        aggregate = "failed"
    elif all(state == "read" for state in states):
        aggregate = "read"
    elif all(state in {"delivered", "read"} for state in states):
        aggregate = "delivered"
    elif all(state in _RECEIPT_STATES for state in states):
        aggregate = "sent"
    else:
        aggregate = None
    conn.execute(
        """
        UPDATE messaging_deliveries
        SET receipt_state = ?, receipt_at_ms = CASE WHEN ? IS NULL THEN NULL ELSE ? END,
            updated_at_ms = MAX(updated_at_ms, ?)
        WHERE delivery_id = ? AND state = 'sent'
        """,
        (aggregate, aggregate, receipt_at_ms, receipt_at_ms, delivery_id),
    )


def sync_record_messaging_delivery_receipt(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    provider_message_id: str,
    receipt_status: MessagingReceiptStatus,
    receipt_at_ms: int,
) -> bool:
    if receipt_status not in _RECEIPT_STATES:
        raise ValidationError("Messaging provider receipt state is invalid.")
    row = conn.execute(
        """
        SELECT delivery.delivery_id
        FROM messaging_deliveries AS delivery
        JOIN messaging_delivery_chunks AS chunk ON chunk.delivery_id = delivery.delivery_id
        WHERE delivery.account_id = ? AND chunk.provider_message_id = ?
        LIMIT 1
        """,
        (account_id, provider_message_id),
    ).fetchone()
    if row is None or not isinstance(row[0], str):
        return False
    delivery_id = row[0]
    changed = _update_chunk_receipt(
        conn,
        delivery_id=delivery_id,
        provider_message_id=provider_message_id,
        receipt_status=receipt_status,
        receipt_at_ms=receipt_at_ms,
    )
    if changed:
        _project_delivery_receipt(
            conn,
            delivery_id=delivery_id,
            receipt_at_ms=receipt_at_ms,
        )
    return changed


def sync_apply_deferred_messaging_receipt(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    provider_message_id: str,
) -> bool:
    row = conn.execute(
        """
        SELECT provider_receipt_state, COALESCE(provider_timestamp_ms, processed_at_ms)
        FROM messaging_ingress_events
        WHERE account_id = ? AND provider_message_id = ?
          AND provider_receipt_state IS NOT NULL
        ORDER BY CASE provider_receipt_state
                     WHEN 'failed' THEN 4 WHEN 'read' THEN 3
                     WHEN 'delivered' THEN 2 ELSE 1
                 END DESC,
                 COALESCE(provider_timestamp_ms, processed_at_ms) DESC
        LIMIT 1
        """,
        (account_id, provider_message_id),
    ).fetchone()
    if row is None or not isinstance(row[1], int):
        return False
    receipt_status = normalize_messaging_receipt_status(row[0])
    if receipt_status is None:
        return False
    return sync_record_messaging_delivery_receipt(
        conn,
        account_id=account_id,
        provider_message_id=provider_message_id,
        receipt_status=receipt_status,
        receipt_at_ms=row[1],
    )
