"""SoAI - Database schema for WebUI device sessions [backend/database/schema_scripts/webui_sessions_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.users.identity_mutation_contract import (
    IDENTITY_MUTATION_TYPES,
    SESSION_ROTATION_POST_COMMIT_MIN_MS,
    sql_values,
)
from core.validation.epoch import EPOCH_MS_MAX, EPOCH_MS_MIN
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.sql.script import execute_sql_script

__all__ = ("apply_webui_sessions_schema", "build_webui_sessions_schema_sql")


def build_webui_sessions_schema_sql() -> str:
    operation_types = sql_values(IDENTITY_MUTATION_TYPES)
    return f"""
        CREATE TABLE IF NOT EXISTS webui_device_sessions (
            jti TEXT PRIMARY KEY CHECK(length(jti) BETWEEN 1 AND 128),
            user_id INTEGER NOT NULL REFERENCES webui_users(id) ON DELETE CASCADE,
            device_id TEXT CHECK(device_id IS NULL OR length(device_id) = 36),
            device_label TEXT NOT NULL CHECK(length(trim(device_label)) BETWEEN 1 AND 80),
            client_type TEXT NOT NULL CHECK(client_type IN ('web', 'android')),
            user_agent TEXT NOT NULL CHECK(length(user_agent) <= 512),
            password_revision INTEGER NOT NULL
                CHECK(password_revision BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            created_at_ms INTEGER NOT NULL
                CHECK(created_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            last_seen_at_ms INTEGER NOT NULL
                CHECK(last_seen_at_ms BETWEEN created_at_ms AND {EPOCH_MS_MAX}),
            expires_at_ms INTEGER NOT NULL
                CHECK(expires_at_ms BETWEEN created_at_ms + 1 AND {EPOCH_MS_MAX}),
            revoked_at_ms INTEGER
                CHECK(revoked_at_ms IS NULL OR revoked_at_ms BETWEEN created_at_ms AND {EPOCH_MS_MAX}),
            CHECK(
                (client_type = 'web' AND device_id IS NULL)
                OR (client_type = 'android' AND device_id IS NOT NULL)
            )
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_webui_device_sessions_user_activity
            ON webui_device_sessions(user_id, revoked_at_ms, expires_at_ms, last_seen_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_webui_device_sessions_expiry
            ON webui_device_sessions(expires_at_ms);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_webui_device_sessions_active_android_installation
            ON webui_device_sessions(user_id, device_id)
            WHERE device_id IS NOT NULL AND revoked_at_ms IS NULL;
        CREATE TABLE IF NOT EXISTS webui_session_rotations (
            source_jti TEXT PRIMARY KEY CHECK(length(source_jti) BETWEEN 1 AND 128),
            replacement_jti TEXT NOT NULL UNIQUE
                CHECK(length(replacement_jti) BETWEEN 1 AND 128),
            operation_id TEXT NOT NULL,
            operation_type TEXT NOT NULL CHECK(operation_type IN ({operation_types})),
            user_id INTEGER NOT NULL REFERENCES webui_users(id) ON DELETE CASCADE,
            source_password_revision INTEGER NOT NULL
                CHECK(source_password_revision BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            source_expires_at_ms INTEGER NOT NULL
                CHECK(source_expires_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            replacement_password_revision INTEGER NOT NULL
                CHECK(replacement_password_revision BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            replacement_issued_at_ms INTEGER NOT NULL
                CHECK(replacement_issued_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            replacement_expires_at_ms INTEGER NOT NULL
                CHECK(replacement_expires_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            rotated_at_ms INTEGER NOT NULL
                CHECK(rotated_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            recoverable_until_ms INTEGER NOT NULL
                CHECK(recoverable_until_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            UNIQUE(user_id, operation_id),
            CHECK(source_jti != replacement_jti),
            CHECK(
                (operation_type = 'username_rename'
                    AND replacement_password_revision = source_password_revision)
                OR (operation_type = 'password_change'
                    AND replacement_password_revision = source_password_revision + 1)
            ),
            CHECK(replacement_issued_at_ms <= rotated_at_ms),
            CHECK(rotated_at_ms < recoverable_until_ms),
            CHECK(recoverable_until_ms <= source_expires_at_ms),
            CHECK(recoverable_until_ms <= replacement_expires_at_ms),
            CHECK(recoverable_until_ms - rotated_at_ms >= {SESSION_ROTATION_POST_COMMIT_MIN_MS})
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_webui_session_rotations_user
            ON webui_session_rotations(user_id, rotated_at_ms);
        CREATE INDEX IF NOT EXISTS idx_webui_session_rotations_cleanup
            ON webui_session_rotations(
                source_expires_at_ms,
                replacement_expires_at_ms,
                recoverable_until_ms
            );
    """


def apply_webui_sessions_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, build_webui_sessions_schema_sql())
