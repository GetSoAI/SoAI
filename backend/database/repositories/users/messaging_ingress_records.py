"""SoAI - Messaging ingress dedupe records [backend/database/repositories/users/messaging_ingress_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ConflictError

if TYPE_CHECKING:
    from core.messaging.ingress_models import NormalizedMessagingEvent
    from core.types.json import JSONDict

__all__ = ("find_messaging_ingress_replay", "insert_messaging_ingress_record")


def find_messaging_ingress_replay(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    provider_event_id: str,
    content_fingerprint: str,
) -> JSONDict | None:
    row = conn.execute(
        """
        SELECT ingress_id, content_fingerprint, outcome, classification,
               linked_input_id, old_conv_id, result_conv_id, diagnostic_code
        FROM messaging_ingress_events
        WHERE account_id = ? AND provider_event_id = ?
        """,
        (account_id, provider_event_id),
    ).fetchone()
    if row is None:
        return None
    if row[1] != content_fingerprint:
        raise ConflictError("Messaging provider event fingerprint changed on replay.")
    return {
        "status": "duplicate",
        "ingress_id": row[0],
        "classification": row[3],
        "outcome": row[2],
        "input_id": row[4],
        "old_conv_id": row[5],
        "conv_id": row[6],
        "diagnostic_code": row[7],
    }


def insert_messaging_ingress_record(
    conn: sqlite3.Connection,
    *,
    ingress_id: str,
    account_id: str,
    user_id: int,
    event: NormalizedMessagingEvent,
    content_fingerprint: str,
    classification: str,
    outcome: str,
    sender_id: str | None,
    diagnostic_code: str | None,
    accepted_at_ms: int,
) -> None:
    conn.execute(
        """
        INSERT INTO messaging_ingress_events (
            ingress_id, account_id, user_id, platform, remote_thread_type,
            remote_thread_key, provider_event_id, provider_message_id,
            discord_dispatch_sequence,
            provider_timestamp_ms,
            content_fingerprint, sender_id, provider_receipt_state,
            classification, outcome,
            diagnostic_code, received_at_ms, processed_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ingress_id,
            account_id,
            user_id,
            event.platform,
            event.remote_thread_type,
            event.remote_thread_key,
            event.provider_event_id,
            event.provider_message_id,
            event.discord_dispatch_sequence,
            event.provider_timestamp_ms,
            content_fingerprint,
            sender_id,
            event.receipt_status,
            classification,
            outcome,
            diagnostic_code,
            accepted_at_ms,
            accepted_at_ms,
        ),
    )
