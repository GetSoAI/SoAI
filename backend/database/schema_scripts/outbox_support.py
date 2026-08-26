"""SoAI - Shared transactional outbox schema helpers [backend/database/schema_scripts/outbox_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import StateError, ValidationError
from core.validation.epoch import EPOCH_MS_MIN
from database.core.sql_builders import validate_sql_identifier

__all__ = ("apply_transactional_outbox_schema",)


def _require_identifier(value: str, *, label: str) -> str:
    if not isinstance(value, str):
        raise StateError(f"Invalid {label}: {value!r}")
    try:
        return validate_sql_identifier(value, label=label)
    except ValidationError as exception:
        raise StateError(f"Invalid {label}: {value!r}") from exception


def apply_transactional_outbox_schema(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    pending_index_name: str,
    processing_index_name: str,
    extra_columns_sql: str = "",
) -> None:
    if not isinstance(extra_columns_sql, str):
        raise StateError(f"Invalid extra columns SQL: {extra_columns_sql!r}")
    normalized_table_name = _require_identifier(table_name, label="table name")
    normalized_pending_index_name = _require_identifier(
        pending_index_name,
        label="pending index name",
    )
    normalized_processing_index_name = _require_identifier(
        processing_index_name,
        label="processing index name",
    )
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {normalized_table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            {extra_columns_sql}event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL CHECK(json_valid(payload_json) AND json_type(payload_json) = 'object'),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'published', 'failed')),
            attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_at_ms INTEGER NOT NULL DEFAULT 0
                CHECK(next_attempt_at_ms = 0 OR next_attempt_at_ms >= {EPOCH_MS_MIN}),
            processing_started_at_ms INTEGER CHECK(processing_started_at_ms IS NULL OR processing_started_at_ms >= {EPOCH_MS_MIN}),
            published_at_ms INTEGER CHECK(published_at_ms IS NULL OR published_at_ms >= {EPOCH_MS_MIN}),
            last_error TEXT
        )
        STRICT
        """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS {normalized_pending_index_name}
        ON {normalized_table_name} (status, next_attempt_at_ms, id)
        """)
    conn.execute(f"""
        CREATE INDEX IF NOT EXISTS {normalized_processing_index_name}
        ON {normalized_table_name} (status, processing_started_at_ms, id)
        """)
