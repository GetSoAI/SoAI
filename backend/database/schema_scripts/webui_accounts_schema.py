"""SoAI - WebUI account schema ownership [backend/database/schema_scripts/webui_accounts_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.users.account_types import webui_account_type_sql_values
from core.validation.epoch import EPOCH_MS_MAX, EPOCH_MS_MIN
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.sql.script import execute_sql_script


def build_webui_accounts_schema_sql() -> str:
    account_type_sql_values = webui_account_type_sql_values()
    return f"""
        CREATE TABLE IF NOT EXISTS webui_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT
                CHECK(id BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            username TEXT NOT NULL UNIQUE
                CHECK(length(username) BETWEEN 3 AND 50)
                CHECK(username = lower(username))
                CHECK(username NOT GLOB '*[^a-z0-9_.-]*'),
            account_type TEXT NOT NULL CHECK(account_type IN ({account_type_sql_values})),
            hashed_password TEXT NOT NULL CHECK(length(hashed_password) > 0),
            is_admin INTEGER NOT NULL CHECK(is_admin IN (0, 1)),
            created_at_ms INTEGER NOT NULL
                CHECK(created_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            password_changed_at_ms INTEGER NOT NULL
                CHECK(password_changed_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            password_revision INTEGER NOT NULL
                CHECK(password_revision BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            workspace_path TEXT NOT NULL CHECK(length(workspace_path) > 0),
            default_workspace_path TEXT NOT NULL UNIQUE
                CHECK(length(default_workspace_path) BETWEEN 1 AND 1024)
                CHECK(substr(default_workspace_path, 1, 16) = 'data/user_files/')
                CHECK(instr(default_workspace_path, char(0)) = 0)
                CHECK(instr(default_workspace_path, char(92)) = 0)
                CHECK(instr(default_workspace_path, ':') = 0)
                CHECK(substr(default_workspace_path, 1, 1) != '/')
                CHECK(substr(default_workspace_path, -1, 1) != '/')
                CHECK(instr('/' || default_workspace_path || '/', '//') = 0)
                CHECK(instr('/' || default_workspace_path || '/', '/./') = 0)
                CHECK(instr('/' || default_workspace_path || '/', '/../') = 0),
            identity_revision INTEGER NOT NULL
                CHECK(identity_revision BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            preferences TEXT CHECK(preferences IS NULL OR json_valid(preferences))
        ) STRICT;
        CREATE TRIGGER IF NOT EXISTS trg_webui_users_account_type_immutable
        BEFORE UPDATE OF account_type ON webui_users
        FOR EACH ROW WHEN NEW.account_type != OLD.account_type
        BEGIN
            SELECT RAISE(ABORT, 'webui account type is immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_users_default_workspace_immutable
        BEFORE UPDATE OF default_workspace_path ON webui_users
        FOR EACH ROW WHEN NEW.default_workspace_path != OLD.default_workspace_path
        BEGIN
            SELECT RAISE(ABORT, 'webui default workspace is immutable');
        END;
    """


def apply_webui_accounts_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, build_webui_accounts_schema_sql())


__all__ = (
    "apply_webui_accounts_schema",
    "build_webui_accounts_schema_sql",
)
