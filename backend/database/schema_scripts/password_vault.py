"""SoAI - Database schema: WebUI password vault [backend/database/schema_scripts/password_vault.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN

__all__ = ("apply_password_vault_schema",)


def apply_password_vault_schema(conn: sqlite3.Connection) -> None:
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS webui_password_vault_credentials (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            scope_json TEXT NOT NULL CHECK(json_valid(scope_json)),
            username_hint TEXT,
            username_encrypted TEXT,
            password_encrypted TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            last_used_at_ms INTEGER,
            UNIQUE(user_id, label),
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        )
        STRICT
        """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_webui_password_vault_credentials_user_created
        ON webui_password_vault_credentials (user_id, created_at_ms DESC)
        """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_webui_password_vault_credentials_user_label
        ON webui_password_vault_credentials (user_id, label)
        """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_webui_password_vault_credentials_user_label_ci
        ON webui_password_vault_credentials (user_id, lower(label))
        """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_webui_password_vault_credentials_user_last_used
        ON webui_password_vault_credentials (user_id, last_used_at_ms)
        """)
