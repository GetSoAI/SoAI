"""SoAI - Fenced Messaging provider request authorization [backend/database/repositories/users/messaging_delivery_request_start.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.repositories.users.messaging_delivery_state_transitions import (
    DELIVERY_CLAIM_WHERE,
)

__all__ = ("sync_mark_messaging_chunk_request_started",)


def sync_mark_messaging_chunk_request_started(
    conn: sqlite3.Connection,
    delivery_id: str,
    claim_generation: int,
    claim_owner: str,
    server_boot_id: str,
    ordinal: int,
    credential_fingerprint: str,
    started_at_ms: int,
) -> bool:
    updated = conn.execute(
        f"""
        UPDATE messaging_delivery_chunks AS chunk
        SET request_started_at_ms = ?, updated_at_ms = ?
        WHERE chunk.delivery_id = ? AND chunk.ordinal = ?
          AND chunk.state = 'sending' AND chunk.request_started_at_ms IS NULL
          AND EXISTS (
              SELECT 1
              FROM messaging_deliveries AS delivery
              JOIN messaging_accounts AS account
                ON account.account_id = delivery.account_id
               AND account.user_id = delivery.user_id
              JOIN messaging_thread_bindings AS binding
                ON binding.account_id = delivery.account_id
               AND binding.user_id = delivery.user_id
               AND binding.remote_thread_type = delivery.remote_thread_type
               AND binding.remote_thread_key = delivery.remote_thread_key
              LEFT JOIN messaging_authorized_senders AS sender
                ON sender.account_id = delivery.account_id
               AND sender.user_id = delivery.user_id
               AND sender.sender_id = delivery.originating_sender_id
              WHERE {DELIVERY_CLAIM_WHERE}
                AND delivery.account_generation = account.lifecycle_generation
                AND delivery.binding_generation = binding.binding_generation
                AND account.lifecycle_state IN ('enabled', 'degraded')
                AND (account.accept_messages_from_anyone = 1
                     OR sender.sender_id IS NOT NULL)
                AND account.credential_fingerprint = ?
          )
        """,
        (
            started_at_ms,
            started_at_ms,
            delivery_id,
            ordinal,
            delivery_id,
            claim_generation,
            claim_owner,
            server_boot_id,
            credential_fingerprint,
        ),
    ).rowcount
    return updated == 1
