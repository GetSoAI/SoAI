"""SoAI - Database schema: tool call live events [backend/database/schema_scripts/tool_call_live_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.schema_scripts.tool_payload_contract_sql import (
    live_tool_payload_invalid_condition,
)
from database.sql.script import execute_sql_script

__all__ = ("apply_tool_call_live_events_schema",)


def _build_tool_call_live_events_schema_sql() -> str:
    tool_payload_invalid_condition = live_tool_payload_invalid_condition()
    return f"""
        CREATE TABLE IF NOT EXISTS webui_tool_call_live_events (
            conv_id TEXT NOT NULL,
            assistant_turn_at_ms INTEGER NOT NULL CHECK(assistant_turn_at_ms >= {EPOCH_MS_MIN}),
            model_variant_index INTEGER NOT NULL CHECK(model_variant_index >= 0),
            call_id TEXT NOT NULL,
            live_sequence INTEGER NOT NULL CHECK(live_sequence >= 0),
            assistant_at_ms INTEGER NOT NULL CHECK(assistant_at_ms >= {EPOCH_MS_MIN}),
            event_type TEXT NOT NULL CHECK(length(trim(event_type)) > 0),
            payload_json TEXT NOT NULL CHECK(json_valid(payload_json) AND json_type(payload_json) = 'object'),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            duration_ms INTEGER CHECK(duration_ms IS NULL OR duration_ms >= 0),
            status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'cancelled', 'error')),
            projection_revision INTEGER NOT NULL CHECK(projection_revision >= 1),
            PRIMARY KEY(conv_id, assistant_turn_at_ms, model_variant_index, call_id, live_sequence),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE
        ) STRICT;
        CREATE TRIGGER IF NOT EXISTS trg_webui_tool_call_live_events_sequence_contiguous
        BEFORE INSERT ON webui_tool_call_live_events
        FOR EACH ROW
        BEGIN
            SELECT
                CASE
                    WHEN NEW.live_sequence != (
                        SELECT COALESCE(MAX(live_sequence) + 1, 0)
                        FROM webui_tool_call_live_events
                        WHERE conv_id = NEW.conv_id
                          AND assistant_turn_at_ms = NEW.assistant_turn_at_ms
                          AND model_variant_index = NEW.model_variant_index
                          AND call_id = NEW.call_id
                    )
                    THEN RAISE(ABORT, 'webui_tool_call_live_events.live_sequence must be contiguous starting at 0')
                END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_tool_call_live_events_payload_contract
        BEFORE INSERT ON webui_tool_call_live_events
        FOR EACH ROW
        BEGIN
            SELECT
                CASE
                    WHEN {tool_payload_invalid_condition}
                    THEN RAISE(ABORT, 'webui_tool_call_live_events payload contract is invalid')
                END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_webui_tool_call_live_events_payload_update_contract
        BEFORE UPDATE OF call_id, payload_json ON webui_tool_call_live_events
        FOR EACH ROW
        BEGIN
            SELECT
                CASE
                    WHEN {tool_payload_invalid_condition}
                    THEN RAISE(ABORT, 'webui_tool_call_live_events payload contract is invalid')
                END;
        END;
        CREATE INDEX IF NOT EXISTS idx_tool_call_live_events_page
            ON webui_tool_call_live_events(conv_id, assistant_turn_at_ms, model_variant_index, call_id, live_sequence DESC);
        CREATE INDEX IF NOT EXISTS idx_tool_call_live_events_assistant
            ON webui_tool_call_live_events(conv_id, assistant_at_ms, call_id, live_sequence);
        """


def apply_tool_call_live_events_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _build_tool_call_live_events_schema_sql())
