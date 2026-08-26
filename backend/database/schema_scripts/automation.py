"""SoAI - Database schema: automation tables [backend/database/schema_scripts/automation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_automation_schema",)


def apply_automation_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS automations (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            title TEXT NOT NULL CHECK(length(trim(title)) > 0),
            color TEXT CHECK(color IS NULL OR length(trim(color)) > 0),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            last_modified_at_ms INTEGER NOT NULL CHECK(last_modified_at_ms >= {EPOCH_MS_MIN}),
            timezone TEXT NOT NULL CHECK(length(trim(timezone)) > 0),
            start_local TEXT NOT NULL CHECK(length(trim(start_local)) > 0),
            recurrence TEXT NOT NULL CHECK(recurrence IN ('none', 'hourly', 'daily', 'weekly', 'monthly', 'yearly')),
            next_run_at_ms INTEGER CHECK(next_run_at_ms IS NULL OR next_run_at_ms >= {EPOCH_MS_MIN}),
            model_settings TEXT NOT NULL CHECK(json_valid(model_settings) AND json_type(model_settings) = 'object'),
            turns_json TEXT NOT NULL CHECK(json_valid(turns_json) AND json_type(turns_json) = 'array'),
            max_turns INTEGER NOT NULL DEFAULT 1 CHECK(max_turns >= 1 AND max_turns <= 1000),
            max_turn_chars INTEGER NOT NULL DEFAULT 20000 CHECK(max_turn_chars > 0),
            max_run_minutes INTEGER NOT NULL DEFAULT 30 CHECK(max_run_minutes >= 1 AND max_run_minutes <= 1440),
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_automations_due
            ON automations(enabled, next_run_at_ms);
        CREATE INDEX IF NOT EXISTS idx_automations_user_modified
            ON automations(user_id, last_modified_at_ms);
        CREATE TABLE IF NOT EXISTS automation_runs (
            id TEXT PRIMARY KEY,
            automation_id TEXT NOT NULL,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            owner_task_id TEXT,
            scheduled_at_ms INTEGER NOT NULL CHECK(scheduled_at_ms >= {EPOCH_MS_MIN}),
            started_at_ms INTEGER CHECK(started_at_ms IS NULL OR started_at_ms >= {EPOCH_MS_MIN}),
            finished_at_ms INTEGER CHECK(finished_at_ms IS NULL OR finished_at_ms >= {EPOCH_MS_MIN}),
            status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'error', 'cancelled', 'abandoned')),
            status_message TEXT,
            conv_id TEXT,
            result_excerpt TEXT,
            color_snapshot TEXT CHECK(color_snapshot IS NULL OR length(trim(color_snapshot)) > 0),
            turns_snapshot TEXT NOT NULL CHECK(json_valid(turns_snapshot) AND json_type(turns_snapshot) = 'array'),
            model_settings_snapshot TEXT NOT NULL CHECK(json_valid(model_settings_snapshot) AND json_type(model_settings_snapshot) = 'object'),
            limits_snapshot TEXT NOT NULL CHECK(json_valid(limits_snapshot) AND json_type(limits_snapshot) = 'object'),
            FOREIGN KEY(automation_id) REFERENCES automations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE SET NULL,
            UNIQUE(automation_id, scheduled_at_ms)
        ) STRICT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_automation_runs_active_per_automation
            ON automation_runs(automation_id)
            WHERE status IN ('queued', 'running');
        CREATE INDEX IF NOT EXISTS idx_automation_runs_user_time
            ON automation_runs(user_id, scheduled_at_ms);
        CREATE INDEX IF NOT EXISTS idx_automation_runs_auto_time
            ON automation_runs(automation_id, scheduled_at_ms);
        CREATE INDEX IF NOT EXISTS idx_automation_runs_status_time
            ON automation_runs(status, scheduled_at_ms);
        CREATE INDEX IF NOT EXISTS idx_automation_runs_owner_task
            ON automation_runs(owner_task_id);
        CREATE TABLE IF NOT EXISTS automation_occurrence_deletions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            automation_id TEXT NOT NULL,
            scheduled_at_ms INTEGER NOT NULL CHECK(scheduled_at_ms >= {EPOCH_MS_MIN}),
            deleted_at_ms INTEGER NOT NULL CHECK(deleted_at_ms >= {EPOCH_MS_MIN}),
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE,
            FOREIGN KEY(automation_id) REFERENCES automations(id) ON DELETE CASCADE,
            UNIQUE(user_id, automation_id, scheduled_at_ms)
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_automation_occurrence_deletions_user_time
            ON automation_occurrence_deletions(user_id, scheduled_at_ms);
        CREATE INDEX IF NOT EXISTS idx_automation_occurrence_deletions_auto_time
            ON automation_occurrence_deletions(automation_id, scheduled_at_ms);
        """,
    )
