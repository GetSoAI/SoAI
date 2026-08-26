"""SoAI - Plugin clone transaction schema [backend/database/schema_scripts/plugin_clone_transactions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.sql.script import execute_sql_script

__all__ = ("apply_plugin_clone_schema",)


def apply_plugin_clone_schema(connection: sqlite3.Connection) -> None:
    execute_sql_script(
        connection,
        """
        CREATE TABLE IF NOT EXISTS plugin_clone_transactions (
            task_id TEXT PRIMARY KEY,
            source_plugin_name TEXT NOT NULL,
            requested_target_name TEXT,
            target_plugin_name TEXT NOT NULL,
            clone_models INTEGER NOT NULL CHECK(clone_models IN (0, 1)),
            phase TEXT NOT NULL DEFAULT 'admitted' CHECK(phase IN ('admitted', 'staging', 'staged', 'publishing', 'registering', 'committed', 'rollback_pending', 'recovery_required', 'rolled_back')),
            committed INTEGER NOT NULL DEFAULT 0 CHECK(committed IN (0, 1)),
            recovery_error TEXT,
            created_at_ms INTEGER NOT NULL
        ) STRICT;
        CREATE TABLE IF NOT EXISTS plugin_clone_target_reservations (
            target_plugin_name TEXT PRIMARY KEY,
            task_id TEXT NOT NULL UNIQUE,
            FOREIGN KEY(task_id) REFERENCES plugin_clone_transactions(task_id) ON DELETE CASCADE,
            FOREIGN KEY(task_id) REFERENCES mutation_admissions(accepted_task_id) ON DELETE RESTRICT
        ) STRICT;
        CREATE TABLE IF NOT EXISTS plugin_clone_artifacts (
            artifact_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            artifact_type TEXT NOT NULL CHECK(artifact_type IN ('plugin_package', 'models', 'configuration', 'database_record', 'runtime', 'environment', 'package_cache')),
            staging_path TEXT NOT NULL,
            final_path TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'intended' CHECK(state IN ('intended', 'materialized', 'published', 'removed')),
            UNIQUE(task_id, artifact_type, final_path),
            FOREIGN KEY(task_id) REFERENCES plugin_clone_transactions(task_id) ON DELETE CASCADE
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_plugin_clone_artifacts_task
        ON plugin_clone_artifacts(task_id, state);
        """,
    )
