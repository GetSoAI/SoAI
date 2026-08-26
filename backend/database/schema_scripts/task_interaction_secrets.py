"""SoAI - Task-owned encrypted interaction secret handoff schema [backend/database/schema_scripts/task_interaction_secrets.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_task_interaction_secrets_schema",)


def apply_task_interaction_secrets_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS task_interaction_secret_handoffs (
            task_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL CHECK(user_id > 0),
            conv_id TEXT NOT NULL,
            checkpoint_generation INTEGER NOT NULL CHECK(checkpoint_generation >= 0),
            secret_ciphertext TEXT CHECK(secret_ciphertext IS NULL OR length(trim(secret_ciphertext)) > 0),
            state TEXT NOT NULL CHECK(state IN (
                'resolution_staged', 'pending', 'claimed', 'downstream_started',
                'effect_unknown', 'expired'
            )),
            claim_generation INTEGER NOT NULL DEFAULT 0 CHECK(claim_generation >= 0),
            claimed_by TEXT,
            downstream_tool_call_id TEXT,
            downstream_started_at_ms INTEGER
                CHECK(downstream_started_at_ms IS NULL OR downstream_started_at_ms >= {EPOCH_MS_MIN}),
            expires_at_ms INTEGER NOT NULL CHECK(expires_at_ms >= {EPOCH_MS_MIN}),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            CHECK(state != 'claimed' OR (claimed_by IS NOT NULL AND claim_generation > 0)),
            CHECK(state != 'downstream_started' OR (
                claimed_by IS NOT NULL AND claim_generation > 0
                AND downstream_tool_call_id IS NOT NULL
                AND downstream_started_at_ms IS NOT NULL
            )),
            CHECK(state IN ('effect_unknown', 'expired') OR secret_ciphertext IS NOT NULL),
            CHECK(state NOT IN ('effect_unknown', 'expired') OR secret_ciphertext IS NULL),
            FOREIGN KEY(task_id) REFERENCES unified_tasks(task_id) ON DELETE CASCADE,
            FOREIGN KEY(conv_id) REFERENCES webui_conversations(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES webui_users(id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_task_interaction_secrets_expiry
            ON task_interaction_secret_handoffs(state, expires_at_ms);
        """,
    )
