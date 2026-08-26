"""SoAI - Database schema: context compaction metric events [backend/database/schema_scripts/context_compaction_metric_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_context_compaction_metric_events_schema",)


def _build_context_compaction_metric_events_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS webui_context_compaction_metric_events (
            storage_call_id TEXT PRIMARY KEY
                CHECK(length(trim(storage_call_id)) > 0)
                REFERENCES webui_chat_tool_calls(id) ON DELETE CASCADE,
            conv_id TEXT NOT NULL
                CHECK(length(trim(conv_id)) > 0)
                REFERENCES webui_conversations(id) ON DELETE CASCADE,
            assistant_turn_at_ms INTEGER NOT NULL CHECK(assistant_turn_at_ms >= {EPOCH_MS_MIN}),
            model_variant_index INTEGER NOT NULL CHECK(model_variant_index >= 0),
            status TEXT NOT NULL CHECK(status IN ('completed', 'cancelled', 'error')),
            tokens_saved INTEGER NOT NULL DEFAULT 0 CHECK(tokens_saved >= 0),
            recorded_at_ms INTEGER NOT NULL CHECK(recorded_at_ms >= {EPOCH_MS_MIN})
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_context_compaction_metric_events_conv_recorded
            ON webui_context_compaction_metric_events(conv_id, recorded_at_ms);
        CREATE INDEX IF NOT EXISTS idx_context_compaction_metric_events_recorded
            ON webui_context_compaction_metric_events(recorded_at_ms);
        CREATE TRIGGER IF NOT EXISTS trg_context_compaction_metric_events_parent_insert
        BEFORE INSERT ON webui_context_compaction_metric_events
        FOR EACH ROW
        BEGIN
            SELECT
                CASE
                    WHEN NOT EXISTS (
                        SELECT 1
                        FROM webui_chat_tool_calls
                        WHERE id = NEW.storage_call_id AND conv_id = NEW.conv_id
                    )
                    THEN RAISE(ABORT, 'context compaction metric event parent mismatch')
                END;
        END;
        CREATE TRIGGER IF NOT EXISTS trg_context_compaction_metric_events_parent_update
        BEFORE UPDATE ON webui_context_compaction_metric_events
        FOR EACH ROW
        BEGIN
            SELECT
                CASE
                    WHEN NOT EXISTS (
                        SELECT 1
                        FROM webui_chat_tool_calls
                        WHERE id = NEW.storage_call_id AND conv_id = NEW.conv_id
                    )
                    THEN RAISE(ABORT, 'context compaction metric event parent mismatch')
                END;
        END;
        """


def apply_context_compaction_metric_events_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _build_context_compaction_metric_events_schema_sql())
