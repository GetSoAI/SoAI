"""SoAI - WebUI chat storage schema ownership [backend/database/schema_scripts/webui_chat_storage_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.schema_scripts.assistant_usage_triggers_sql import (
    ASSISTANT_USAGE_TRIGGER_SQL,
)
from database.sql.script import execute_sql_script


def build_webui_chat_storage_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS webui_system_settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS webui_chat_identity_defaults (
            user_id INTEGER PRIMARY KEY CHECK(user_id > 0),
            user_display_name TEXT,
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE TABLE IF NOT EXISTS webui_chat_model_defaults (
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            model_id TEXT NOT NULL CHECK(length(trim(model_id)) > 0),
            assistant_display_name TEXT, user_system_prompt TEXT,
            soai_system_prompt_enabled INTEGER NOT NULL DEFAULT 1 CHECK(soai_system_prompt_enabled IN (0, 1)),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            PRIMARY KEY (user_id, model_id),
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE TABLE IF NOT EXISTS webui_conversations (
            id TEXT PRIMARY KEY, user_id INTEGER NOT NULL CHECK(user_id > 0),
            title TEXT NOT NULL CHECK(length(trim(title)) > 0),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            last_modified_at_ms INTEGER NOT NULL CHECK(last_modified_at_ms >= {EPOCH_MS_MIN}),
            model_settings TEXT NOT NULL CHECK(json_valid(model_settings) AND json_type(model_settings) = 'object'),
            color TEXT CHECK(color IS NULL OR length(trim(color)) > 0),
            is_favorite INTEGER NOT NULL DEFAULT 0 CHECK(is_favorite IN (0, 1)),
            is_automation INTEGER NOT NULL DEFAULT 0 CHECK(is_automation IN (0, 1)),
            is_messaging INTEGER NOT NULL DEFAULT 0 CHECK(is_messaging IN (0, 1)),
            messaging_platform TEXT CHECK(messaging_platform IS NULL OR messaging_platform IN ('telegram', 'whatsapp', 'discord')),
            messaging_account_label TEXT CHECK(messaging_account_label IS NULL OR length(trim(messaging_account_label)) > 0),
            messaging_account_snapshot_id TEXT CHECK(messaging_account_snapshot_id IS NULL OR length(trim(messaging_account_snapshot_id)) > 0),
            is_archived INTEGER NOT NULL DEFAULT 0 CHECK(is_archived IN (0, 1)),
            input_generation INTEGER NOT NULL DEFAULT 0 CHECK(input_generation >= 0),
            message_count INTEGER NOT NULL DEFAULT 0 CHECK(message_count >= 0),
            CHECK(is_automation = 0 OR is_messaging = 0),
            CHECK(
                (is_messaging = 1 AND messaging_platform IS NOT NULL
                    AND messaging_account_label IS NOT NULL
                    AND messaging_account_snapshot_id IS NOT NULL)
                OR (is_messaging = 0 AND messaging_platform IS NULL
                    AND messaging_account_label IS NULL
                    AND messaging_account_snapshot_id IS NULL)
            ),
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_conversations_user_modified
            ON webui_conversations(user_id, last_modified_at_ms);
        CREATE INDEX IF NOT EXISTS idx_conversations_user_archived_modified
            ON webui_conversations(user_id, is_archived, last_modified_at_ms DESC, id DESC);
        CREATE TABLE IF NOT EXISTS webui_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, conv_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system', 'developer', 'tool')),
            message_type TEXT NOT NULL DEFAULT 'chat' CHECK(message_type IN ('chat', 'control')),
            content TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            assistant_turn_at_ms INTEGER CHECK(assistant_turn_at_ms IS NULL OR assistant_turn_at_ms >= {EPOCH_MS_MIN}),
            model_variant_index INTEGER CHECK(model_variant_index IS NULL OR model_variant_index >= 0),
            content_length INTEGER CHECK(content_length IS NULL OR content_length >= 0),
            content_sha256 TEXT CHECK(content_sha256 IS NULL OR length(content_sha256) = 64),
            finalized_at_ms INTEGER CHECK(finalized_at_ms IS NULL OR finalized_at_ms >= {EPOCH_MS_MIN}),
            request_id TEXT, model_id TEXT, prompt_tokens INTEGER,
            completion_tokens INTEGER, total_tokens INTEGER, usage_source TEXT,
            generation_latency_ms INTEGER, finish_reason TEXT,
            thinking_tail_duration_ms INTEGER CHECK(thinking_tail_duration_ms IS NULL OR thinking_tail_duration_ms >= 0),
            CHECK(
                (role = 'assistant' AND assistant_turn_at_ms IS NOT NULL AND model_variant_index IS NOT NULL)
                OR (role != 'assistant' AND assistant_turn_at_ms IS NULL AND model_variant_index IS NULL)
            ),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_id
            ON webui_messages(conv_id, created_at_ms, id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_assistant_request_id
            ON webui_messages(conv_id, request_id)
            WHERE role = 'assistant' AND request_id IS NOT NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_assistant_turn_variant
            ON webui_messages(conv_id, assistant_turn_at_ms, model_variant_index)
            WHERE role = 'assistant';
        CREATE TABLE IF NOT EXISTS webui_conversation_attention (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assistant_message_id INTEGER NOT NULL UNIQUE,
            FOREIGN KEY(assistant_message_id) REFERENCES webui_messages(id) ON DELETE CASCADE
        ) STRICT;
        CREATE TRIGGER IF NOT EXISTS trg_webui_messages_count_insert
        AFTER INSERT ON webui_messages FOR EACH ROW
        BEGIN
            UPDATE webui_conversations SET message_count = message_count + 1 WHERE id = NEW.conv_id;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_messages_count_delete
        AFTER DELETE ON webui_messages FOR EACH ROW
        BEGIN
            UPDATE webui_conversations
            SET message_count = CASE WHEN message_count > 0 THEN message_count - 1 ELSE 0 END
            WHERE id = OLD.conv_id;
        END;
        CREATE TABLE IF NOT EXISTS webui_prompts (
            id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            modified_at_ms INTEGER NOT NULL CHECK(modified_at_ms >= {EPOCH_MS_MIN}),
            color TEXT,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_prompts_user_color ON webui_prompts(user_id, color);
    """


def apply_webui_chat_storage_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, build_webui_chat_storage_schema_sql())
    execute_sql_script(conn, ASSISTANT_USAGE_TRIGGER_SQL)


__all__ = (
    "apply_webui_chat_storage_schema",
    "build_webui_chat_storage_schema_sql",
)
