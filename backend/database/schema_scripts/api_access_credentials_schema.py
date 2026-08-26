"""SoAI - API access credential schema ownership [backend/database/schema_scripts/api_access_credentials_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script


def build_api_access_credentials_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS openai_api_keys (
            key_id TEXT PRIMARY KEY, hashed_key_ciphertext TEXT NOT NULL,
            salt TEXT NOT NULL, fingerprint TEXT NOT NULL, label TEXT NOT NULL,
            prefix TEXT NOT NULL, scopes TEXT NOT NULL CHECK(json_valid(scopes)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            created_by INTEGER, expires_at_ms INTEGER, rotation_reminder_at_ms INTEGER,
            revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0, 1)),
            revoked_at_ms INTEGER, revoked_by INTEGER, encryption_version INTEGER NOT NULL,
            last_used_at_ms INTEGER, last_used_ip TEXT,
            request_count INTEGER NOT NULL DEFAULT 0,
            rate_limited_count INTEGER NOT NULL DEFAULT 0, assigned_user_id INTEGER,
            FOREIGN KEY(created_by) REFERENCES webui_users(id) ON DELETE SET NULL,
            FOREIGN KEY(revoked_by) REFERENCES webui_users(id) ON DELETE SET NULL,
            FOREIGN KEY(assigned_user_id) REFERENCES webui_users(id) ON DELETE SET NULL
        ) STRICT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_openai_api_keys_fingerprint ON openai_api_keys(fingerprint);
        CREATE INDEX IF NOT EXISTS idx_openai_api_keys_revoked_expires ON openai_api_keys(revoked, expires_at_ms);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_openai_api_keys_assigned_user
            ON openai_api_keys(assigned_user_id) WHERE assigned_user_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_openai_api_keys_created_by ON openai_api_keys(created_by);
        CREATE INDEX IF NOT EXISTS idx_openai_api_keys_revoked_by ON openai_api_keys(revoked_by);
        CREATE TABLE IF NOT EXISTS mcp_access_tokens (
            token_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES webui_users(id) ON DELETE CASCADE,
            hashed_token_ciphertext TEXT NOT NULL, salt TEXT NOT NULL,
            fingerprint TEXT NOT NULL, label TEXT NOT NULL, prefix TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            last_used_at_ms INTEGER, expires_at_ms INTEGER,
            revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0, 1)),
            revoked_at_ms INTEGER,
            revoked_by INTEGER REFERENCES webui_users(id) ON DELETE SET NULL,
            encryption_version INTEGER NOT NULL,
            CHECK((revoked = 0 AND revoked_at_ms IS NULL AND revoked_by IS NULL) OR (revoked = 1 AND revoked_at_ms IS NOT NULL))
        ) STRICT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mcp_access_tokens_fingerprint
            ON mcp_access_tokens(fingerprint);
        CREATE INDEX IF NOT EXISTS idx_mcp_access_tokens_user_created
            ON mcp_access_tokens(user_id, created_at_ms DESC, token_id DESC);
        CREATE INDEX IF NOT EXISTS idx_mcp_access_tokens_user_revoked
            ON mcp_access_tokens(user_id, revoked, created_at_ms DESC, token_id DESC);
        CREATE TABLE IF NOT EXISTS openai_api_key_quota_config (
            key_id TEXT PRIMARY KEY REFERENCES openai_api_keys(key_id) ON DELETE CASCADE,
            mode TEXT NOT NULL DEFAULT 'none' CHECK(mode IN ('none', 'tokens', 'requests')),
            hourly_limit_units INTEGER, hourly_window_hours INTEGER,
            daily_limit_units INTEGER, weekly_limit_units INTEGER, monthly_limit_units INTEGER,
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN})
        ) STRICT;
        CREATE TABLE IF NOT EXISTS openai_api_key_quota_usage_windows (
            key_id TEXT NOT NULL REFERENCES openai_api_keys(key_id) ON DELETE CASCADE,
            window_name TEXT NOT NULL CHECK(window_name IN ('hourly', 'daily', 'weekly', 'monthly')),
            window_ms INTEGER NOT NULL CHECK(window_ms > 0),
            window_start_at_ms INTEGER NOT NULL CHECK(window_start_at_ms >= {EPOCH_MS_MIN}),
            used_units INTEGER NOT NULL DEFAULT 0 CHECK(used_units >= 0),
            reserved_units INTEGER NOT NULL DEFAULT 0 CHECK(reserved_units >= 0),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            PRIMARY KEY (key_id, window_name)
        ) STRICT;
        CREATE TABLE IF NOT EXISTS openai_api_key_quota_finalizations (
            reservation_id TEXT PRIMARY KEY,
            key_id TEXT NOT NULL REFERENCES openai_api_keys(key_id) ON DELETE CASCADE,
            finalized_at_ms INTEGER NOT NULL CHECK(finalized_at_ms >= {EPOCH_MS_MIN}),
            charged_units INTEGER NOT NULL, released_units INTEGER NOT NULL
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_openai_api_key_quota_finalizations_key ON openai_api_key_quota_finalizations(key_id);
        CREATE TABLE IF NOT EXISTS openai_api_key_quota_reservations (
            reservation_id TEXT NOT NULL,
            key_id TEXT NOT NULL REFERENCES openai_api_keys(key_id) ON DELETE CASCADE,
            window_name TEXT NOT NULL CHECK(window_name IN ('hourly', 'daily', 'weekly', 'monthly')),
            estimate_units INTEGER NOT NULL CHECK(estimate_units >= 0),
            reserved_at_ms INTEGER NOT NULL CHECK(reserved_at_ms >= {EPOCH_MS_MIN}),
            expires_at_ms INTEGER NOT NULL CHECK(expires_at_ms >= {EPOCH_MS_MIN}),
            status TEXT NOT NULL CHECK(status IN ('reserved', 'finalized', 'expired')),
            finalized_at_ms INTEGER CHECK(finalized_at_ms IS NULL OR finalized_at_ms >= {EPOCH_MS_MIN}),
            charged_units INTEGER NOT NULL DEFAULT 0, released_units INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (reservation_id, window_name)
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_openai_api_key_quota_reservations_status_expires
            ON openai_api_key_quota_reservations(status, expires_at_ms);
        CREATE INDEX IF NOT EXISTS idx_openai_api_key_quota_reservations_key_status_expires
            ON openai_api_key_quota_reservations(key_id, status, expires_at_ms);
    """


def apply_api_access_credentials_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, build_api_access_credentials_schema_sql())


__all__ = (
    "apply_api_access_credentials_schema",
    "build_api_access_credentials_schema_sql",
)
