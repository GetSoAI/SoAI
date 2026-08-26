"""SoAI - Database schema: chat prompt history [backend/database/schema_scripts/chat_prompt_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.conversations.conversation_draft_content_validation import (
    CHAT_COMPOSER_TEXT_MAX_LENGTH,
)
from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_chat_prompt_history_schema",)


def _build_chat_prompt_history_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS webui_chat_prompt_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            source_input_id TEXT NOT NULL UNIQUE,
            text TEXT NOT NULL CHECK(
                text = trim(text)
                AND length(text) BETWEEN 1 AND {CHAT_COMPOSER_TEXT_MAX_LENGTH}
            ),
            accepted_at_ms INTEGER NOT NULL CHECK(accepted_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_webui_chat_prompt_history_user
            ON webui_chat_prompt_history(user_id, id DESC);
        """


def apply_chat_prompt_history_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _build_chat_prompt_history_schema_sql())
