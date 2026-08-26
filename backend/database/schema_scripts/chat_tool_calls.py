"""SoAI - Database schema: chat tool calls [backend/database/schema_scripts/chat_tool_calls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_chat_tool_calls_schema",)


def _build_chat_tool_calls_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS webui_chat_tool_calls (
            id TEXT PRIMARY KEY,
            call_id TEXT NOT NULL,
            conv_id TEXT NOT NULL,
            turn_id TEXT,
            iteration_index INTEGER CHECK(iteration_index IS NULL OR iteration_index >= 0),
            message_index INTEGER CHECK(message_index IS NULL OR message_index >= 0),
            assistant_at_ms INTEGER CHECK(assistant_at_ms IS NULL OR assistant_at_ms >= {EPOCH_MS_MIN}),
            assistant_turn_at_ms INTEGER NOT NULL CHECK(assistant_turn_at_ms >= {EPOCH_MS_MIN}),
            model_variant_index INTEGER NOT NULL CHECK(model_variant_index >= 0),
            tool_name TEXT NOT NULL,
            tool_arguments TEXT CHECK(tool_arguments IS NULL OR json_valid(tool_arguments)),
            tool_result TEXT CHECK(tool_result IS NULL OR json_valid(tool_result)),
            owner_task_id TEXT CHECK(owner_task_id IS NULL OR length(trim(owner_task_id)) > 0),
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'cancelled', 'error')),
            error_message TEXT,
            duration_ms INTEGER NOT NULL DEFAULT 0 CHECK(duration_ms >= 0),
            started_at_ms INTEGER CHECK(started_at_ms IS NULL OR started_at_ms >= {EPOCH_MS_MIN}),
            live_revision INTEGER NOT NULL DEFAULT 0 CHECK(live_revision >= 0),
            last_live_event_at_ms INTEGER CHECK(last_live_event_at_ms IS NULL OR last_live_event_at_ms >= {EPOCH_MS_MIN}),
            last_live_sequence INTEGER CHECK(last_live_sequence IS NULL OR last_live_sequence >= 0),
            sequence_index INTEGER NOT NULL CHECK(sequence_index >= 0),
            content_index_before INTEGER NOT NULL CHECK(content_index_before >= 0),
            thinking_index_before INTEGER NOT NULL CHECK(thinking_index_before >= 0),
            thinking_duration_before_ms INTEGER CHECK(thinking_duration_before_ms IS NULL OR thinking_duration_before_ms >= 0),
            collapsed INTEGER NOT NULL DEFAULT 1 CHECK(collapsed IN (0, 1)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            completed_at_ms INTEGER CHECK(completed_at_ms IS NULL OR completed_at_ms >= {EPOCH_MS_MIN}),
            CHECK(((status IN ('pending', 'running')) AND completed_at_ms IS NULL) OR ((status IN ('completed', 'cancelled', 'error')) AND completed_at_ms IS NOT NULL)),
            CHECK(status NOT IN ('cancelled', 'error') OR (error_message IS NOT NULL AND length(trim(error_message)) > 0)),
            CHECK(status != 'pending' OR duration_ms = 0),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            UNIQUE(conv_id, assistant_turn_at_ms, model_variant_index, sequence_index)
        ) STRICT;
        CREATE TRIGGER IF NOT EXISTS trg_webui_chat_tool_calls_sequence_contiguous
        BEFORE INSERT ON webui_chat_tool_calls
        FOR EACH ROW
        BEGIN
                SELECT
                    CASE
                        WHEN NEW.sequence_index != (
                            SELECT COUNT(*)
                            FROM webui_chat_tool_calls
                            WHERE conv_id = NEW.conv_id
                              AND assistant_turn_at_ms = NEW.assistant_turn_at_ms
                              AND model_variant_index = NEW.model_variant_index
                        )
                        THEN RAISE(ABORT, 'webui_chat_tool_calls.sequence_index must be contiguous starting at 0')
            END;
        END;
        CREATE INDEX IF NOT EXISTS idx_tool_calls_message ON webui_chat_tool_calls(conv_id, message_index);
        CREATE INDEX IF NOT EXISTS idx_tool_calls_assistant_at_ms
            ON webui_chat_tool_calls(conv_id, assistant_at_ms, sequence_index, created_at_ms, id);
        CREATE INDEX IF NOT EXISTS idx_tool_calls_assistant_turn_variant
            ON webui_chat_tool_calls(conv_id, assistant_turn_at_ms, model_variant_index, sequence_index);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tool_calls_assistant_turn_call_id
            ON webui_chat_tool_calls(conv_id, assistant_turn_at_ms, model_variant_index, call_id);
        CREATE INDEX IF NOT EXISTS idx_tool_calls_turn_iteration ON webui_chat_tool_calls(conv_id, turn_id, iteration_index, sequence_index);
        CREATE INDEX IF NOT EXISTS idx_tool_calls_owner_task ON webui_chat_tool_calls(owner_task_id);
        CREATE INDEX IF NOT EXISTS idx_tool_calls_conversation_live_activity_order
            ON webui_chat_tool_calls(
                conv_id, status, COALESCE(started_at_ms, created_at_ms) DESC,
                created_at_ms DESC, sequence_index DESC, call_id ASC
            );
        """


def apply_chat_tool_calls_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _build_chat_tool_calls_schema_sql())
