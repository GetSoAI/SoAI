"""SoAI - Database schema: OpenAI Conversations storage tables [backend/database/schema_scripts/openai_conversations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_openai_conversations_schema",)


def apply_openai_conversations_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS openai_conversations (
            conversation_id TEXT PRIMARY KEY,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
            deleted_at_ms INTEGER CHECK(deleted_at_ms IS NULL OR deleted_at_ms >= {EPOCH_MS_MIN}),
            user_id INTEGER REFERENCES webui_users(id) ON DELETE SET NULL,
            api_key_id TEXT REFERENCES openai_api_keys(key_id) ON DELETE SET NULL
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_openai_conversations_owner_created
            ON openai_conversations(user_id, api_key_id, created_at_ms DESC, conversation_id DESC);

        CREATE TABLE IF NOT EXISTS openai_conversation_items (
            item_id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES openai_conversations(conversation_id) ON DELETE RESTRICT,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            item_json TEXT NOT NULL CHECK(json_valid(item_json)),
            deleted_at_ms INTEGER CHECK(deleted_at_ms IS NULL OR deleted_at_ms >= {EPOCH_MS_MIN}),
            user_id INTEGER REFERENCES webui_users(id) ON DELETE SET NULL,
            api_key_id TEXT REFERENCES openai_api_keys(key_id) ON DELETE SET NULL
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_openai_conversation_items_conversation_created
            ON openai_conversation_items(conversation_id, created_at_ms DESC, item_id DESC);
        CREATE INDEX IF NOT EXISTS idx_openai_conversation_items_owner_created
            ON openai_conversation_items(user_id, api_key_id, created_at_ms DESC, item_id DESC);
        """,
    )
