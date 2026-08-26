"""SoAI - WebUI chat preset V1 schema [backend/database/schema_scripts/webui_chat_presets_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MAX, EPOCH_MS_MIN
from core.validation.javascript_integer import JAVASCRIPT_SAFE_INTEGER_MAX
from database.sql.script import execute_sql_script

__all__ = (
    "apply_webui_chat_presets_schema",
    "build_webui_chat_presets_schema_sql",
)


def build_webui_chat_presets_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS webui_chat_presets (
            id TEXT PRIMARY KEY
                CHECK(length(id) = 39)
                CHECK(substr(id, 1, 7) = 'preset_')
                CHECK(length(substr(id, 8)) = 32)
                CHECK(substr(id, 8) NOT GLOB '*[^0-9a-f]*'),
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL
                CHECK(name = trim(name))
                CHECK(length(name) BETWEEN 1 AND 255),
            name_key TEXT NOT NULL CHECK(length(name_key) > 0),
            sections_json TEXT NOT NULL
                CHECK(json_valid(sections_json))
                CHECK(json_type(sections_json) = 'object'),
            revision INTEGER NOT NULL
                CHECK(revision BETWEEN 1 AND {JAVASCRIPT_SAFE_INTEGER_MAX}),
            created_at_ms INTEGER NOT NULL
                CHECK(created_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX}),
            modified_at_ms INTEGER NOT NULL
                CHECK(modified_at_ms BETWEEN {EPOCH_MS_MIN} AND {EPOCH_MS_MAX})
                CHECK(modified_at_ms >= created_at_ms),
            UNIQUE(user_id, name_key),
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_webui_chat_presets_user_list
            ON webui_chat_presets(user_id, modified_at_ms DESC, name_key, id);
    """


def apply_webui_chat_presets_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, build_webui_chat_presets_schema_sql())
