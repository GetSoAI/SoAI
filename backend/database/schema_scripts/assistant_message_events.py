"""SoAI - Database schema: assistant message events [backend/database/schema_scripts/assistant_message_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.schema_scripts.tool_payload_contract_sql import (
    assistant_timeline_tool_payload_invalid_condition,
)
from database.sql.script import execute_sql_script

__all__ = ("apply_assistant_message_events_schema",)


def _build_assistant_message_events_schema_sql() -> str:
    tool_payload_invalid_condition = assistant_timeline_tool_payload_invalid_condition()
    return f"""
        CREATE TABLE IF NOT EXISTS webui_assistant_message_events (
            conv_id TEXT NOT NULL,
            assistant_at_ms INTEGER NOT NULL CHECK(assistant_at_ms >= {EPOCH_MS_MIN}),
            sequence INTEGER NOT NULL CHECK(sequence >= 0),
            assistant_revision INTEGER NOT NULL CHECK(assistant_revision = sequence + 1),
            event_type TEXT NOT NULL CHECK(length(trim(event_type)) > 0),
            payload_json TEXT NOT NULL CHECK(json_valid(payload_json) AND json_type(payload_json) = 'object'),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            PRIMARY KEY (conv_id, assistant_at_ms, sequence),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        CREATE INDEX IF NOT EXISTS idx_webui_assistant_message_events_prompt_projection
            ON webui_assistant_message_events(conv_id, assistant_at_ms, event_type, sequence);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_webui_assistant_message_events_completed_tool_call_id_unique
            ON webui_assistant_message_events(
                conv_id,
                assistant_at_ms,
                json_extract(payload_json, '$.tool.call_id')
            )
            WHERE event_type = 'tool_call_completed'
              AND json_extract(payload_json, '$.tool.call_id') IS NOT NULL;
        CREATE TRIGGER IF NOT EXISTS trg_webui_assistant_message_events_contiguous
        BEFORE INSERT ON webui_assistant_message_events
        FOR EACH ROW
        BEGIN
            SELECT
                CASE
                    WHEN NEW.sequence != (
                        SELECT COALESCE(MAX(sequence), -1) + 1
                        FROM webui_assistant_message_events
                        WHERE conv_id = NEW.conv_id AND assistant_at_ms = NEW.assistant_at_ms
                    )
                    THEN RAISE(ABORT, 'webui_assistant_message_events.sequence must be contiguous starting at 0')
                END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_assistant_message_events_unfinished
        BEFORE INSERT ON webui_assistant_message_events
        FOR EACH ROW
        BEGIN
            SELECT
                CASE
                    WHEN NOT EXISTS (
                        SELECT 1
                        FROM webui_messages
                        WHERE conv_id = NEW.conv_id
                          AND created_at_ms = NEW.assistant_at_ms
                          AND role = 'assistant'
                          AND finalized_at_ms IS NULL
                    )
                    THEN RAISE(ABORT, 'webui_assistant_message_events cannot append to missing or finalized assistant message')
                END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_assistant_message_events_revision
        BEFORE INSERT ON webui_assistant_message_events
        FOR EACH ROW
        BEGIN
            SELECT
                CASE
                    WHEN NEW.assistant_revision != (NEW.sequence + 1)
                    THEN RAISE(ABORT, 'webui_assistant_message_events.assistant_revision must equal sequence + 1')
                END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_assistant_message_events_tool_payload_contract
        BEFORE INSERT ON webui_assistant_message_events
        WHEN NEW.event_type IN ('tool_call_created', 'tool_call_started', 'tool_call_completed')
        BEGIN
            SELECT
                CASE
                    WHEN {tool_payload_invalid_condition}
                    THEN RAISE(ABORT, 'webui_assistant_message_events tool payload contract is invalid')
                END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_assistant_message_events_tool_payload_update_contract
        BEFORE UPDATE OF event_type, payload_json ON webui_assistant_message_events
        WHEN NEW.event_type IN ('tool_call_created', 'tool_call_started', 'tool_call_completed')
        BEGIN
            SELECT
                CASE
                    WHEN {tool_payload_invalid_condition}
                    THEN RAISE(ABORT, 'webui_assistant_message_events tool payload contract is invalid')
                END;
        END;
        """


def apply_assistant_message_events_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _build_assistant_message_events_schema_sql())
