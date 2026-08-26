"""SoAI - Database schema: conversation drafts [backend/database/schema_scripts/conversation_drafts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.conversations.conversation_draft_content_validation import (
    CHAT_COMPOSER_TEXT_MAX_LENGTH,
)
from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_conversation_drafts_schema",)


def _build_conversation_drafts_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS webui_conversation_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            text TEXT NOT NULL DEFAULT ''
                CHECK(length(text) <= {CHAT_COMPOSER_TEXT_MAX_LENGTH}),
            source_text TEXT NOT NULL DEFAULT ''
                CHECK(length(source_text) <= {CHAT_COMPOSER_TEXT_MAX_LENGTH}),
            attachment_content_json TEXT NOT NULL DEFAULT '[]'
                CHECK(json_valid(attachment_content_json) AND json_type(attachment_content_json)='array'),
            is_deleted INTEGER NOT NULL DEFAULT 0 CHECK(is_deleted IN (0, 1)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            client_id TEXT NOT NULL CHECK(length(trim(client_id)) BETWEEN 1 AND 128),
            client_sequence INTEGER NOT NULL CHECK(client_sequence >= 0),
            revision INTEGER NOT NULL CHECK(revision >= 1),
            UNIQUE(conv_id, user_id),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_webui_conversation_drafts_updated
            ON webui_conversation_drafts(user_id, updated_at_ms DESC, id DESC);
        CREATE TABLE IF NOT EXISTS webui_conversation_draft_mutations (
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            client_id TEXT NOT NULL CHECK(length(trim(client_id)) BETWEEN 1 AND 128),
            client_sequence INTEGER NOT NULL CHECK(client_sequence >= 0),
            payload_signature TEXT NOT NULL CHECK(length(payload_signature) = 64),
            result_revision INTEGER NOT NULL CHECK(result_revision >= 1),
            PRIMARY KEY(conv_id, user_id, client_id, client_sequence),
            FOREIGN KEY(conv_id, user_id)
                REFERENCES webui_conversation_drafts(conv_id, user_id) ON DELETE CASCADE
        ) STRICT;
        """


def apply_conversation_drafts_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _build_conversation_drafts_schema_sql())
