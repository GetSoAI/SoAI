"""SoAI - Atomic Messaging chunk-attempt scheduling [backend/database/repositories/users/messaging_delivery_claims.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.messaging.delivery_models import MessagingDeliveryAttempt
from database.core.sqlite_row_scalars import (
    require_sqlite_row_int,
    require_sqlite_row_non_empty_str,
    require_sqlite_row_str,
)
from database.repositories.users.messaging_delivery_state_transitions import (
    sync_terminalize_messaging_delivery,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform

__all__ = ("sync_claim_next_messaging_delivery_attempt",)

ROW_LABEL = "Messaging delivery claim"


def _select_candidate(
    conn: sqlite3.Connection,
    claimed_at_ms: int,
) -> sqlite3.Row | None:
    row = conn.execute(
        """
        SELECT delivery.delivery_id
        FROM messaging_deliveries AS delivery
        WHERE delivery.state = 'pending' AND delivery.next_attempt_at_ms <= ?
          AND NOT EXISTS (
              SELECT 1 FROM messaging_deliveries AS earlier
              WHERE earlier.account_id = delivery.account_id
                AND earlier.remote_thread_type = delivery.remote_thread_type
                AND earlier.remote_thread_key = delivery.remote_thread_key
                AND earlier.state IN ('pending', 'sending')
                AND (earlier.created_at_ms, earlier.delivery_id)
                    < (delivery.created_at_ms, delivery.delivery_id)
          )
        ORDER BY delivery.next_attempt_at_ms, delivery.created_at_ms,
                 delivery.delivery_id
        LIMIT 1
        """,
        (claimed_at_ms,),
    ).fetchone()
    if row is None:
        return None
    if not isinstance(row, sqlite3.Row):
        raise StateError("Messaging delivery candidate row is invalid.")
    return row


def _read_candidate_attempt(
    conn: sqlite3.Connection,
    delivery_id: str,
) -> sqlite3.Row | None:
    row = conn.execute(
        """
        SELECT delivery.delivery_id, delivery.account_id, delivery.user_id,
               delivery.remote_thread_type, delivery.remote_thread_key,
               delivery.originating_sender_id, delivery.account_generation,
               delivery.binding_generation, account.platform,
               account.lifecycle_state, account.lifecycle_generation,
               binding.binding_generation AS current_binding_generation,
               CASE WHEN account.accept_messages_from_anyone = 1
                         OR sender.sender_id IS NOT NULL THEN 1 ELSE 0 END AS authorized,
               chunk.ordinal, chunk.content_text, chunk.attempt_count,
               (SELECT COUNT(*) FROM messaging_delivery_chunks AS prior
                WHERE prior.delivery_id = delivery.delivery_id
                  AND prior.ordinal < chunk.ordinal AND prior.state != 'sent')
                    AS invalid_prior_count,
               (SELECT COUNT(*) FROM messaging_delivery_chunks AS invalid
                WHERE invalid.delivery_id = delivery.delivery_id
                  AND invalid.state NOT IN ('sent', 'pending')) AS invalid_state_count
        FROM messaging_deliveries AS delivery
        LEFT JOIN messaging_accounts AS account
          ON account.account_id = delivery.account_id AND account.user_id = delivery.user_id
        LEFT JOIN messaging_thread_bindings AS binding
          ON binding.account_id = delivery.account_id AND binding.user_id = delivery.user_id
         AND binding.remote_thread_type = delivery.remote_thread_type
         AND binding.remote_thread_key = delivery.remote_thread_key
        LEFT JOIN messaging_authorized_senders AS sender
          ON sender.account_id = delivery.account_id AND sender.user_id = delivery.user_id
         AND sender.sender_id = delivery.originating_sender_id
        LEFT JOIN messaging_delivery_chunks AS chunk
          ON chunk.delivery_id = delivery.delivery_id
         AND chunk.ordinal = (
             SELECT MIN(candidate.ordinal) FROM messaging_delivery_chunks AS candidate
             WHERE candidate.delivery_id = delivery.delivery_id
               AND candidate.state != 'sent'
         )
        WHERE delivery.delivery_id = ? AND delivery.state = 'pending'
        """,
        (delivery_id,),
    ).fetchone()
    if row is None:
        return None
    if not isinstance(row, sqlite3.Row):
        raise StateError("Messaging delivery attempt row is invalid.")
    return row


def _terminalize_candidate(
    conn: sqlite3.Connection,
    *,
    delivery_id: str,
    state: str,
    failure_code: str,
    now_ms: int,
) -> None:
    sync_terminalize_messaging_delivery(
        conn,
        delivery_id=delivery_id,
        expected_state="pending",
        terminal_state=state,
        failure_code=failure_code,
        now_ms=now_ms,
    )


def _candidate_failure(row: sqlite3.Row) -> tuple[str, str] | None:
    if row[9] not in ("enabled", "degraded"):
        return ("skipped", "messaging_account_delivery_closed")
    if row[6] != row[10]:
        return ("skipped", "messaging_account_generation_changed")
    if row[7] != row[11]:
        return ("skipped", "messaging_binding_generation_changed")
    if row[12] != 1:
        return ("skipped", "messaging_sender_revoked")
    if row[13] is None or row[16] != 0 or row[17] != 0:
        return ("failed", "messaging_delivery_chunk_state_invalid")
    if row[8] not in ("telegram", "whatsapp", "discord"):
        return ("failed", "messaging_delivery_platform_invalid")
    if row[14] is None or not isinstance(row[14], str) or not row[14]:
        return ("failed", "messaging_delivery_content_invalid")
    return None


def _materialize_attempt(
    row: sqlite3.Row,
    claim_generation: int,
    chunk_attempt_count: int,
) -> MessagingDeliveryAttempt:
    values = dict(row)
    platform = values.get("platform")
    normalized_platform: MessagingPlatform
    if platform == "telegram":
        normalized_platform = "telegram"
    elif platform == "whatsapp":
        normalized_platform = "whatsapp"
    elif platform == "discord":
        normalized_platform = "discord"
    else:
        raise StateError("Messaging delivery platform changed during claim.")
    return MessagingDeliveryAttempt(
        delivery_id=require_sqlite_row_non_empty_str(values, "delivery_id", label=ROW_LABEL),
        claim_generation=claim_generation,
        ordinal=require_sqlite_row_int(values, "ordinal", label=ROW_LABEL),
        content_text=require_sqlite_row_str(values, "content_text", label=ROW_LABEL),
        chunk_attempt_count=chunk_attempt_count,
        account_id=require_sqlite_row_non_empty_str(values, "account_id", label=ROW_LABEL),
        account_generation=require_sqlite_row_int(
            values,
            "account_generation",
            label=ROW_LABEL,
        ),
        user_id=require_sqlite_row_int(values, "user_id", label=ROW_LABEL, minimum=1),
        platform=normalized_platform,
        remote_thread_type=require_sqlite_row_non_empty_str(
            values,
            "remote_thread_type",
            label=ROW_LABEL,
        ),
        remote_thread_key=require_sqlite_row_non_empty_str(
            values,
            "remote_thread_key",
            label=ROW_LABEL,
        ),
        binding_generation=require_sqlite_row_int(
            values,
            "binding_generation",
            label=ROW_LABEL,
        ),
        originating_sender_id=require_sqlite_row_non_empty_str(
            values,
            "originating_sender_id",
            label=ROW_LABEL,
        ),
    )


def sync_claim_next_messaging_delivery_attempt(
    conn: sqlite3.Connection,
    claim_owner: str,
    server_boot_id: str,
    claimed_at_ms: int,
) -> MessagingDeliveryAttempt | None:
    while True:
        candidate = _select_candidate(conn, claimed_at_ms)
        if candidate is None:
            return None
        delivery_id = require_sqlite_row_non_empty_str(
            dict(candidate),
            "delivery_id",
            label=ROW_LABEL,
        )
        row = _read_candidate_attempt(conn, delivery_id)
        if row is None:
            raise StateError("Messaging delivery candidate disappeared during claim.")
        failure = _candidate_failure(row)
        if failure is not None:
            _terminalize_candidate(
                conn,
                delivery_id=delivery_id,
                state=failure[0],
                failure_code=failure[1],
                now_ms=claimed_at_ms,
            )
            continue
        ordinal = require_sqlite_row_int(dict(row), "ordinal", label=ROW_LABEL)
        claimed = conn.execute(
            """
            UPDATE messaging_deliveries
            SET state = 'sending', claim_generation = claim_generation + 1,
                claim_owner = ?, claim_server_boot_id = ?,
                attempt_count = attempt_count + 1,
                started_at_ms = COALESCE(started_at_ms, ?), updated_at_ms = ?
            WHERE delivery_id = ? AND state = 'pending'
            RETURNING claim_generation
            """,
            (claim_owner, server_boot_id, claimed_at_ms, claimed_at_ms, delivery_id),
        ).fetchone()
        if claimed is None:
            raise StateError("Messaging delivery candidate changed during claim.")
        if not isinstance(claimed, sqlite3.Row):
            raise StateError("Messaging delivery claim generation row is invalid.")
        chunk = conn.execute(
            """
            UPDATE messaging_delivery_chunks
            SET state = 'sending', attempt_count = attempt_count + 1,
                request_started_at_ms = NULL, updated_at_ms = ?
            WHERE delivery_id = ? AND ordinal = ? AND state = 'pending'
            RETURNING attempt_count
            """,
            (claimed_at_ms, delivery_id, ordinal),
        ).fetchone()
        if chunk is None:
            raise StateError("Messaging delivery selected chunk changed during claim.")
        if not isinstance(chunk, sqlite3.Row):
            raise StateError("Messaging delivery chunk attempt count is invalid.")
        claim_generation = require_sqlite_row_int(
            dict(claimed),
            "claim_generation",
            label=ROW_LABEL,
            minimum=1,
        )
        chunk_attempt_count = require_sqlite_row_int(
            dict(chunk),
            "attempt_count",
            label=ROW_LABEL,
            minimum=1,
        )
        return _materialize_attempt(row, claim_generation, chunk_attempt_count)
