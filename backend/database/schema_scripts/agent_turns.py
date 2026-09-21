"""SoAI - Database schema: agent turn state [backend/database/schema_scripts/agent_turns.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_agent_turns_schema",)


def _build_agent_turns_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS webui_agent_turns (
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            turn_id TEXT NOT NULL,
            turn_scope TEXT NOT NULL DEFAULT 'root' CHECK(turn_scope IN ('root', 'subagent')),
            parent_turn_id TEXT,
            parent_tool_call_id TEXT,
            parent_iteration_index INTEGER CHECK(parent_iteration_index IS NULL OR parent_iteration_index >= 0),
            display_name TEXT,
            requested_model TEXT,
            owner_task_id TEXT,
            execution_token TEXT NOT NULL CHECK(length(trim(execution_token)) > 0),
            server_boot_id TEXT NOT NULL CHECK(length(trim(server_boot_id)) > 0),
            status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'cancelled', 'error', 'max_iterations', 'abandoned')),
            mode TEXT NOT NULL CHECK(length(trim(mode)) > 0),
            max_iterations INTEGER NOT NULL CHECK(max_iterations > 0),
            iteration_index INTEGER NOT NULL CHECK(iteration_index >= 0),
            sequence INTEGER NOT NULL CHECK(sequence >= 0),
            turn_cancellation_id TEXT,
            active_inference_cancellation_id TEXT,
            assistant_text TEXT,
            tool_calls_json TEXT NOT NULL CHECK(json_valid(tool_calls_json) AND json_type(tool_calls_json) = 'array'),
            tool_results_json TEXT NOT NULL CHECK(json_valid(tool_results_json) AND json_type(tool_results_json) = 'array'),
            activities_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(activities_json) AND json_type(activities_json) = 'array'),
            reached_max_iterations INTEGER NOT NULL CHECK(reached_max_iterations IN (0, 1)),
            error_message TEXT,
            error_type TEXT,
            token_usage_json TEXT CHECK(token_usage_json IS NULL OR (json_valid(token_usage_json) AND json_type(token_usage_json) = 'object')),
            todo_revision INTEGER NOT NULL CHECK(todo_revision >= 0),
            todo_explanation TEXT,
            todo_json TEXT NOT NULL CHECK(json_valid(todo_json) AND json_type(todo_json) = 'array'),
            started_at_ms INTEGER NOT NULL CHECK(started_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            finished_at_ms INTEGER CHECK(finished_at_ms IS NULL OR finished_at_ms >= {EPOCH_MS_MIN}),
            manual_regeneration_request_json TEXT CHECK(manual_regeneration_request_json IS NULL OR (json_valid(manual_regeneration_request_json) AND json_type(manual_regeneration_request_json) = 'object')),
            manual_regeneration_accepted_revision INTEGER CHECK(manual_regeneration_accepted_revision IS NULL OR manual_regeneration_accepted_revision >= {EPOCH_MS_MIN}) CHECK((manual_regeneration_request_json IS NULL) = (manual_regeneration_accepted_revision IS NULL)),
            CHECK(((turn_scope = 'root') AND parent_turn_id IS NULL AND parent_tool_call_id IS NULL AND parent_iteration_index IS NULL AND owner_task_id IS NULL) OR ((turn_scope = 'subagent') AND parent_turn_id IS NOT NULL AND length(trim(parent_turn_id)) > 0 AND parent_tool_call_id IS NOT NULL AND length(trim(parent_tool_call_id)) > 0 AND parent_iteration_index IS NOT NULL AND owner_task_id IS NOT NULL AND length(trim(owner_task_id)) > 0)),
            CHECK(((status = 'running') AND finished_at_ms IS NULL) OR ((status IN ('completed', 'cancelled', 'error', 'max_iterations', 'abandoned')) AND finished_at_ms IS NOT NULL)),
            CHECK(((status = 'max_iterations') AND reached_max_iterations = 1) OR ((status != 'max_iterations') AND reached_max_iterations = 0)),
            CHECK(updated_at_ms >= started_at_ms),
            CHECK(finished_at_ms IS NULL OR finished_at_ms >= updated_at_ms),
            PRIMARY KEY (conv_id, user_id, turn_id),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
            ) WITHOUT ROWID, STRICT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_turns_single_running_root
            ON webui_agent_turns(conv_id, user_id)
            WHERE turn_scope = 'root' AND status = 'running';
        CREATE INDEX IF NOT EXISTS idx_agent_turns_conversation_latest ON webui_agent_turns(conv_id, user_id, updated_at_ms DESC, turn_id DESC);
        CREATE INDEX IF NOT EXISTS idx_agent_turns_running_root ON webui_agent_turns(conv_id, user_id, turn_scope, status, updated_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_agent_turns_parent_lookup ON webui_agent_turns(conv_id, user_id, parent_turn_id, updated_at_ms DESC, turn_id DESC);
        CREATE INDEX IF NOT EXISTS idx_agent_turns_owner_task ON webui_agent_turns(owner_task_id, updated_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_agent_turns_turn_iteration ON webui_agent_turns(conv_id, turn_id, iteration_index);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_turns_manual_regeneration_identity
            ON webui_agent_turns(
                conv_id,
                user_id,
                json_extract(manual_regeneration_request_json, '$.client_id'),
                json_extract(manual_regeneration_request_json, '$.client_request_id')
            ) WHERE manual_regeneration_request_json IS NOT NULL;
        CREATE TABLE IF NOT EXISTS webui_agent_event_sequences (
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            sequence INTEGER NOT NULL CHECK(sequence >= 0),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            PRIMARY KEY(conv_id, user_id),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS webui_agent_todo_state (
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            revision INTEGER NOT NULL CHECK(revision >= 0),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            explanation TEXT,
            todo_json TEXT NOT NULL CHECK(json_valid(todo_json) AND json_type(todo_json) = 'array'),
            PRIMARY KEY (conv_id, user_id),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS webui_agent_plan (
            conv_id TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            revision INTEGER NOT NULL CHECK(revision >= 0),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            title TEXT,
            markdown TEXT,
            PRIMARY KEY (conv_id, user_id),
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        """


def apply_agent_turns_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _build_agent_turns_schema_sql())
