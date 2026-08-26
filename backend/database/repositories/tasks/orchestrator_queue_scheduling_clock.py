"""SoAI - Durable orchestrator queue scheduling clock allocation [backend/database/repositories/tasks/orchestrator_queue_scheduling_clock.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import require_unix_epoch_ms
from database.core.query_execution import sync_fetch_one_as_dict
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row

__all__ = ("reserve_orchestrator_queue_scheduling_time",)


def reserve_orchestrator_queue_scheduling_time(
    connection: sqlite3.Connection,
    candidate_at_ms: int,
) -> int:
    validated_candidate = require_unix_epoch_ms(
        candidate_at_ms,
        error_message="Queue scheduling timestamp must be a valid epoch-millisecond integer.",
    )
    row = sync_fetch_one_as_dict(
        connection.execute(
            """
            UPDATE orchestrator_queue_scheduling_clock
               SET last_reserved_at_ms = MAX(last_reserved_at_ms, ?)
             WHERE singleton = 1
         RETURNING last_reserved_at_ms
            """,
            (validated_candidate,),
        ),
    )
    if row is None:
        raise sqlite3.IntegrityError("orchestrator_queue_scheduling_clock row is missing")
    return coerce_required_int_from_sqlite_row(row, "last_reserved_at_ms")
