"""SoAI - Database schema: SoAIBench GPU benchmark runs [backend/database/schema_scripts/hardware_soaibench.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.sql.script import execute_sql_script

__all__ = ("apply_hardware_soaibench_schema",)


def apply_hardware_soaibench_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(
        conn,
        """
        CREATE TABLE IF NOT EXISTS hardware_gpu_soaibench_runs (
            run_id TEXT PRIMARY KEY,
            created_by_user_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            gpu_name TEXT,
            gpu_model_key TEXT,
            vendor TEXT,
            driver_version TEXT,
            gpu_uuid TEXT,
            pci_bdf TEXT,
            gpu_index INTEGER,
            profile TEXT NOT NULL CHECK(profile IN ('standard', 'stress')),
            benchmark_mode TEXT NOT NULL DEFAULT 'quick' CHECK(benchmark_mode IN ('quick', 'certified')),
            status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'unstable', 'failed', 'cancelled', 'stopped', 'unsupported', 'indeterminate')),
            score_version TEXT,
            overall_score INTEGER,
            compute_score INTEGER,
            memory_score INTEGER,
            latency_score INTEGER,
            stability_multiplier REAL,
            compute_gops REAL,
            alu_gops REAL,
            matrix_gops REAL,
            memory_gbs REAL,
            latency_us REAL,
            latency_dispatches_per_second REAL,
            started_at_ms INTEGER NOT NULL,
            completed_at_ms INTEGER,
            last_heartbeat_at_ms INTEGER,
            stop_requested_at_ms INTEGER,
            update_seq INTEGER NOT NULL DEFAULT 0,
            duration_ms INTEGER,
            sample_count INTEGER NOT NULL DEFAULT 0,
            settings_snapshot_json TEXT CHECK(settings_snapshot_json IS NULL OR json_valid(settings_snapshot_json)),
            summary_json TEXT CHECK(summary_json IS NULL OR json_valid(summary_json)),
            pass_results_json TEXT CHECK(pass_results_json IS NULL OR json_valid(pass_results_json)),
            environment_json TEXT CHECK(environment_json IS NULL OR json_valid(environment_json)),
            certification_json TEXT CHECK(certification_json IS NULL OR json_valid(certification_json)),
            leaderboard_eligible INTEGER NOT NULL DEFAULT 0 CHECK(leaderboard_eligible IN (0, 1)),
            leaderboard_rejection_reason TEXT,
            score_variance_percent REAL,
            failure_reason TEXT,
            unsupported_reason TEXT,
            created_by_tool TEXT NOT NULL,
            publication_source_supported INTEGER NOT NULL DEFAULT 0 CHECK(publication_source_supported IN (0, 1))
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_hardware_gpu_soaibench_user_device_started
            ON hardware_gpu_soaibench_runs(created_by_user_id, device_id, started_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_hardware_gpu_soaibench_user_uuid_started
            ON hardware_gpu_soaibench_runs(created_by_user_id, gpu_uuid, started_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_hardware_gpu_soaibench_user_pci_started
            ON hardware_gpu_soaibench_runs(created_by_user_id, pci_bdf, started_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_hardware_gpu_soaibench_user_model_started
            ON hardware_gpu_soaibench_runs(created_by_user_id, gpu_model_key, started_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_hardware_gpu_soaibench_status_started
            ON hardware_gpu_soaibench_runs(status, started_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_hardware_gpu_soaibench_profile_started
            ON hardware_gpu_soaibench_runs(profile, started_at_ms DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_hardware_gpu_soaibench_active_device
            ON hardware_gpu_soaibench_runs(device_id)
            WHERE status = 'running';
        CREATE TABLE IF NOT EXISTS hardware_gpu_soaibench_publications (
            run_id TEXT PRIMARY KEY
                CHECK(length(run_id) = 32 AND run_id NOT GLOB '*[^0-9a-f]*'),
            created_by_user_id INTEGER NOT NULL CHECK(created_by_user_id > 0),
            installation_id TEXT NOT NULL
                CHECK(length(installation_id) = 36 AND installation_id = lower(installation_id)),
            canonical_submission_json TEXT NOT NULL
                CHECK(length(CAST(canonical_submission_json AS BLOB)) BETWEEN 2 AND 262144)
                CHECK(json_valid(canonical_submission_json) AND json_type(canonical_submission_json) = 'object'),
            state TEXT NOT NULL CHECK(state IN ('prepared', 'published')),
            prepared_at_ms INTEGER NOT NULL CHECK(prepared_at_ms >= 0),
            published_at_ms INTEGER CHECK(published_at_ms IS NULL OR published_at_ms >= prepared_at_ms),
            receipt_json TEXT
                CHECK(receipt_json IS NULL OR length(CAST(receipt_json AS BLOB)) BETWEEN 2 AND 16384)
                CHECK(receipt_json IS NULL OR (json_valid(receipt_json) AND json_type(receipt_json) = 'object')),
            CHECK(
                (state = 'prepared' AND published_at_ms IS NULL AND receipt_json IS NULL)
                OR
                (state = 'published' AND published_at_ms IS NOT NULL AND receipt_json IS NOT NULL)
            )
        ) STRICT;
        """,
    )
