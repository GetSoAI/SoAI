"""SoAI - Durable mutation admission schema [backend/database/schema_scripts/mutation_admission.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.sql.script import execute_sql_script

__all__ = ("apply_mutation_admission_schema",)


def apply_mutation_admission_schema(connection: sqlite3.Connection) -> None:
    execute_sql_script(
        connection,
        """
        CREATE TABLE IF NOT EXISTS mutation_admissions (
            request_id TEXT PRIMARY KEY,
            accepted_task_id TEXT NOT NULL UNIQUE,
            conflict_keys TEXT NOT NULL CHECK(json_valid(conflict_keys) AND json_type(conflict_keys) = 'array'),
            shared_conflict_keys TEXT NOT NULL CHECK(json_valid(shared_conflict_keys) AND json_type(shared_conflict_keys) = 'array'),
            operation_type TEXT NOT NULL,
            target_identity TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            authorization_scope TEXT NOT NULL,
            command_payload TEXT NOT NULL CHECK(json_valid(command_payload) AND json_type(command_payload) = 'object'),
            schema_discriminator TEXT NOT NULL,
            recovery_payload_encrypted TEXT,
            lifecycle_status TEXT NOT NULL DEFAULT 'accepted' CHECK(lifecycle_status IN ('accepted', 'running', 'completed', 'failed', 'cancelled', 'recovery_required')),
            terminal_result TEXT CHECK(terminal_result IS NULL OR json_valid(terminal_result)),
            claim_owner TEXT,
            lease_expires_at_ms INTEGER,
            fencing_token INTEGER NOT NULL DEFAULT 0 CHECK(fencing_token >= 0),
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
            execution_phase TEXT NOT NULL DEFAULT 'accepted',
            execution_state TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(execution_state) AND json_type(execution_state) = 'object'),
            accepted_at_ms INTEGER NOT NULL,
            expires_at_ms INTEGER NOT NULL CHECK(expires_at_ms > accepted_at_ms),
            completed_at_ms INTEGER,
            FOREIGN KEY(accepted_task_id) REFERENCES unified_tasks(task_id) ON DELETE RESTRICT
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_mutation_admissions_claim
        ON mutation_admissions(lifecycle_status, lease_expires_at_ms, accepted_at_ms);
        CREATE TABLE IF NOT EXISTS mutation_conflict_keys (
            conflict_key TEXT NOT NULL,
            request_id TEXT NOT NULL,
            access_mode TEXT NOT NULL CHECK(access_mode IN ('exclusive', 'shared')),
            reservation_target_name TEXT,
            PRIMARY KEY(conflict_key, request_id),
            CHECK(reservation_target_name IS NULL OR access_mode = 'exclusive'),
            FOREIGN KEY(request_id) REFERENCES mutation_admissions(request_id) ON DELETE CASCADE,
            FOREIGN KEY(reservation_target_name) REFERENCES plugin_clone_target_reservations(target_plugin_name) ON DELETE RESTRICT
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_mutation_conflict_request
        ON mutation_conflict_keys(request_id);
        CREATE TRIGGER IF NOT EXISTS trg_mutation_conflict_access_before_insert
        BEFORE INSERT ON mutation_conflict_keys
        WHEN EXISTS (
            SELECT 1 FROM mutation_conflict_keys AS existing
            WHERE existing.conflict_key = NEW.conflict_key
                AND existing.request_id != NEW.request_id
                AND (existing.access_mode = 'exclusive' OR NEW.access_mode = 'exclusive')
        )
        BEGIN
            SELECT RAISE(ABORT, 'mutation conflict claim collision');
        END;
        CREATE TABLE IF NOT EXISTS mutation_admission_clock (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            server_time_watermark_ms INTEGER NOT NULL CHECK(server_time_watermark_ms >= 0)
        ) STRICT;
        """,
    )
