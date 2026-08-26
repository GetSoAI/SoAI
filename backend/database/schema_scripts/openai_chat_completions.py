"""SoAI - Database schema: OpenAI Chat Completions storage tables [backend/database/schema_scripts/openai_chat_completions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_openai_chat_completions_schema",)


def apply_openai_chat_completions_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS openai_chat_completions (
            completion_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            api_key_id TEXT REFERENCES openai_api_keys(key_id) ON DELETE SET NULL,
            model TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            store INTEGER NOT NULL CHECK(store IN (0, 1)),
            request_json TEXT NOT NULL CHECK(json_valid(request_json)),
            completion_json TEXT NOT NULL CHECK(json_valid(completion_json)),
            metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
            deleted_at_ms INTEGER CHECK(deleted_at_ms IS NULL OR deleted_at_ms >= {EPOCH_MS_MIN})
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_openai_chat_completions_task_id
            ON openai_chat_completions(task_id);
        CREATE INDEX IF NOT EXISTS idx_openai_chat_completions_api_key_id
            ON openai_chat_completions(api_key_id);
        CREATE INDEX IF NOT EXISTS idx_openai_chat_completions_store_created_at
            ON openai_chat_completions(store, created_at_ms DESC, completion_id DESC);
        """,
    )
