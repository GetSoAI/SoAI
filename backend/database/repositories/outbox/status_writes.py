"""SoAI - Outbox status update writers [backend/database/repositories/outbox/status_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
import sqlite3
from typing import TYPE_CHECKING, Literal

from core.errors.exceptions import StateError

if TYPE_CHECKING:
    type OutboxRetryableFailureTable = Literal[
        "plugin_authoritative_state_outbox",
        "webui_domain_event_outbox",
    ]

__all__ = ("sync_record_outbox_row_retryable_failure",)


def _resolve_pending_failure_update_statement(table: OutboxRetryableFailureTable) -> str:
    if not isinstance(table, str):
        raise StateError(f"Unsupported outbox retryable failure table: {table}")
    if re.fullmatch(r"^[A-Za-z_][A-Za-z0-9_]*$", table) is None:
        raise StateError(f"Unsupported outbox retryable failure table: {table}")
    match table:
        case "plugin_authoritative_state_outbox" | "webui_domain_event_outbox":
            return f"""
    UPDATE {table}
    SET
        status = 'pending',
        attempts = ?,
        next_attempt_at_ms = ?,
        last_error = ?,
        processing_started_at_ms = NULL
    WHERE id = ?
    """
    raise StateError(f"Unsupported outbox retryable failure table: {table}")


def sync_record_outbox_row_retryable_failure(
    conn: sqlite3.Connection,
    *,
    table: OutboxRetryableFailureTable,
    outbox_id: int,
    attempts: int,
    next_attempt_at_ms: int,
    error_message: str,
) -> bool:
    statement = _resolve_pending_failure_update_statement(table)
    updated = (
        conn.execute(
            statement,
            (
                int(attempts),
                int(next_attempt_at_ms),
                error_message,
                int(outbox_id),
            ),
        ).rowcount
        > 0
    )
    return updated
