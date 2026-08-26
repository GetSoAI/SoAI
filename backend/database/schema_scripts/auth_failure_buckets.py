"""SoAI - Database schema: authentication failure buckets [backend/database/schema_scripts/auth_failure_buckets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN

__all__ = ("apply_auth_failure_buckets_schema",)


def apply_auth_failure_buckets_schema(conn: sqlite3.Connection) -> None:
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS auth_failure_buckets (
            bucket_id TEXT PRIMARY KEY,
            count INTEGER NOT NULL CHECK(count >= 0),
            window_start_at_ms INTEGER NOT NULL CHECK(window_start_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN})
        )
        WITHOUT ROWID,
        STRICT
        """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_auth_failure_buckets_updated_at
        ON auth_failure_buckets (updated_at_ms)
        """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_auth_failure_buckets_window_start
        ON auth_failure_buckets (window_start_at_ms)
        """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS webui_notification_alert_state (
            alert_id TEXT PRIMARY KEY,
            last_emitted_at_ms INTEGER NOT NULL CHECK(last_emitted_at_ms >= {EPOCH_MS_MIN}),
            pending_count INTEGER NOT NULL CHECK(pending_count >= 0),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN})
        )
        WITHOUT ROWID,
        STRICT
        """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_webui_notification_alert_state_updated_at
        ON webui_notification_alert_state (updated_at_ms)
        """)
