"""SoAI - Database schema for external accounts [backend/database/schema_scripts/external_accounts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.users.account_identifiers import EXTERNAL_ACCOUNT_ID_PREFIX
from database.schema_scripts.oauth2_base_fields_sql import OAUTH2_BASE_FIELDS_SQL
from database.sql.script import execute_sql_script

__all__ = ("apply_external_accounts_schema",)


def apply_external_accounts_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS external_accounts (
            id TEXT PRIMARY KEY NOT NULL CHECK(id GLOB '{EXTERNAL_ACCOUNT_ID_PREFIX}*'),
            user_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            username TEXT NOT NULL,
            auth_type TEXT NOT NULL CHECK(auth_type IN ('password', 'oauth2')),
            password_encrypted TEXT,
            oauth_status TEXT NOT NULL CHECK(
                oauth_status IN (
                    'none',
                    'ready',
                    'auth_required',
                    'insufficient_scope',
                    'expired',
                    'error'
                )
            ) DEFAULT 'none',
{OAUTH2_BASE_FIELDS_SQL}
            oauth_scopes TEXT,
            oauth_required_scopes TEXT,
            created_at_ms INTEGER NOT NULL,
            last_modified_at_ms INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_external_accounts_user_created
            ON external_accounts(user_id, created_at_ms DESC, id DESC);
        CREATE INDEX IF NOT EXISTS idx_external_accounts_user_label
            ON external_accounts(user_id, label COLLATE NOCASE, id DESC);
        """,
    )
