"""SoAI - Database schema: metrics, files, MCP, and task tables [backend/database/schema_scripts/metrics_files_tasks.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.schema_scripts.oauth2_base_fields_sql import OAUTH2_BASE_FIELDS_SQL
from database.sql.script import execute_sql_script

__all__ = ("apply_metrics_files_tasks_schema",)


def apply_metrics_files_tasks_schema(
    conn: sqlite3.Connection,
    *,
    task_type_check: str,
    task_status_check: str,
    active_task_status_check: str,
) -> None:
    execute_sql_script(
        conn,
        f"""
        CREATE TABLE IF NOT EXISTS metrics_live (
            metric_key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN})
        ) STRICT;
        CREATE TABLE IF NOT EXISTS metrics_history (
            observed_at_ms INTEGER NOT NULL CHECK(observed_at_ms >= {EPOCH_MS_MIN}),
            metric_key TEXT NOT NULL,
            value REAL NOT NULL,
            PRIMARY KEY (metric_key, observed_at_ms)
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS hardware_cpu_history (
            observed_at_ms INTEGER NOT NULL CHECK(observed_at_ms >= {EPOCH_MS_MIN}),
            device_id TEXT NOT NULL,
            usage_percent REAL,
            temperature_celsius REAL,
            power_draw_watts REAL,
            memory_percent REAL,
            power_limit_watts REAL,
            PRIMARY KEY (observed_at_ms, device_id)
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS hardware_gpu_history (
            observed_at_ms INTEGER NOT NULL CHECK(observed_at_ms >= {EPOCH_MS_MIN}),
            device_id TEXT NOT NULL,
            gpu_index INTEGER,
            utilization REAL,
            percent_used REAL,
            temperature REAL,
            power_draw_watts REAL,
            power_limit_watts REAL,
            core_clock_mhz REAL,
            mem_clock_mhz REAL,
            PRIMARY KEY (observed_at_ms, device_id)
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS hardware_disk_history (
            observed_at_ms INTEGER NOT NULL CHECK(observed_at_ms >= {EPOCH_MS_MIN}),
            device_id TEXT NOT NULL,
            mount TEXT,
            device TEXT,
            total_bytes INTEGER,
            used_bytes INTEGER,
            free_bytes INTEGER,
            percent_used REAL,
            PRIMARY KEY (observed_at_ms, device_id)
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS hardware_network_history (
            observed_at_ms INTEGER NOT NULL CHECK(observed_at_ms >= {EPOCH_MS_MIN}),
            device_id TEXT NOT NULL,
            interface TEXT,
            bytes_sent INTEGER,
            bytes_recv INTEGER,
            packets_sent INTEGER,
            packets_recv INTEGER,
            errin INTEGER,
            errout INTEGER,
            dropin INTEGER,
            dropout INTEGER,
            upload_mbps REAL,
            download_mbps REAL,
            PRIMARY KEY (observed_at_ms, device_id, interface)
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS system_speed_tests (
            cache_key TEXT PRIMARY KEY,
            path TEXT NOT NULL CHECK(length(trim(path)) > 0),
            sample_bytes INTEGER NOT NULL CHECK(sample_bytes > 0),
            observed_at_ms INTEGER NOT NULL CHECK(observed_at_ms >= {EPOCH_MS_MIN}),
            duration_ms INTEGER NOT NULL CHECK(duration_ms >= 0),
            bytes_processed INTEGER NOT NULL CHECK(bytes_processed >= 0),
            bytes_per_second REAL NOT NULL CHECK(bytes_per_second >= 0.0)
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS real_download_speeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plugin_name TEXT NOT NULL REFERENCES plugins_catalog(plugin_name) ON DELETE CASCADE,
            model_id TEXT NOT NULL,
            bytes_downloaded INTEGER NOT NULL CHECK(bytes_downloaded >= 0),
            duration_ms INTEGER NOT NULL CHECK(duration_ms >= 0),
            bytes_per_second REAL NOT NULL CHECK(bytes_per_second >= 0.0),
            observed_at_ms INTEGER NOT NULL CHECK(observed_at_ms >= {EPOCH_MS_MIN})
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_real_download_speeds_observed
            ON real_download_speeds(observed_at_ms DESC, id DESC);
        CREATE INDEX IF NOT EXISTS idx_real_download_speeds_plugin ON real_download_speeds(plugin_name);
        CREATE INDEX IF NOT EXISTS idx_metrics_history_observed_at
            ON metrics_history(observed_at_ms DESC, metric_key);
        CREATE INDEX IF NOT EXISTS idx_cpu_history_device_observed_at
            ON hardware_cpu_history(device_id, observed_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_gpu_history_device_observed_at
            ON hardware_gpu_history(device_id, observed_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_disk_history_device_observed_at
            ON hardware_disk_history(device_id, observed_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_network_history_device_observed_at
            ON hardware_network_history(device_id, interface, observed_at_ms DESC);
        CREATE TABLE IF NOT EXISTS files_catalog (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL CHECK(length(trim(filename)) > 0),
            purpose TEXT NOT NULL CHECK(length(trim(purpose)) > 0),
            size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
            content_sha256 TEXT NOT NULL CHECK(length(content_sha256) = 64),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            file_path TEXT NOT NULL UNIQUE CHECK(length(trim(file_path)) > 0),
            user_id INTEGER REFERENCES webui_users(id) ON DELETE CASCADE,
            api_key_id TEXT REFERENCES openai_api_keys(key_id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK(status IN ('uploaded', 'processed', 'error', 'active')),
            status_details TEXT
        ) STRICT;
        CREATE TABLE IF NOT EXISTS mcp_servers (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, transport_type TEXT NOT NULL CHECK(transport_type IN ('stdio', 'streamable_http')),
            endpoint TEXT NOT NULL, args TEXT CHECK(args IS NULL OR json_valid(args)),
            env TEXT CHECK(env IS NULL OR json_valid(env)), headers TEXT CHECK(headers IS NULL OR json_valid(headers)),
            auth_type TEXT NOT NULL DEFAULT 'none' CHECK(auth_type IN ('none', 'api_key', 'oauth')),
            api_key_encrypted TEXT,
            oauth_status TEXT NOT NULL DEFAULT 'none' CHECK(oauth_status IN ('none', 'ready', 'auth_required', 'insufficient_scope', 'expired', 'error')),
{OAUTH2_BASE_FIELDS_SQL}
            oauth_scopes TEXT CHECK(oauth_scopes IS NULL OR json_valid(oauth_scopes)),
            oauth_required_scopes TEXT CHECK(oauth_required_scopes IS NULL OR json_valid(oauth_required_scopes)),
            timeout_ms INTEGER NOT NULL DEFAULT 30000, auto_reconnect INTEGER NOT NULL DEFAULT 1 CHECK(auto_reconnect IN (0, 1)),
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)), status TEXT NOT NULL DEFAULT 'disconnected' CHECK(status IN ('disconnected', 'connecting', 'connected', 'error', 'reconnecting', 'auth_required')),
            capabilities TEXT CHECK(capabilities IS NULL OR json_valid(capabilities)), last_error TEXT,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            last_modified_at_ms INTEGER NOT NULL CHECK(last_modified_at_ms >= {EPOCH_MS_MIN})
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_files_purpose ON files_catalog (purpose);
        CREATE INDEX IF NOT EXISTS idx_files_owner_created_at ON files_catalog (user_id, api_key_id, created_at_ms DESC);
        CREATE TABLE IF NOT EXISTS unified_tasks (
            task_id TEXT PRIMARY KEY,
            task_type TEXT NOT NULL CHECK(task_type IN ({task_type_check})),
            status TEXT NOT NULL CHECK(status IN ({task_status_check})),
            user_id INTEGER NOT NULL,
            owner_id TEXT NOT NULL,
            owner_type TEXT NOT NULL CHECK(owner_type IN ('mcp_client', 'http_request', 'conversation', 'system', 'hardware_soaibench')),
            cancellation_id TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN}),
            completed_at_ms INTEGER,
            ttl_ms INTEGER CHECK(ttl_ms IS NULL OR ttl_ms > 0),
            poll_interval_ms INTEGER NOT NULL DEFAULT 1000 CHECK(poll_interval_ms > 0),
            progress_current INTEGER CHECK(progress_current IS NULL OR progress_current >= 0),
            progress_total INTEGER CHECK(progress_total IS NULL OR progress_total >= 0),
            status_message TEXT,
            progress_details TEXT,
            metadata TEXT CHECK(metadata IS NULL OR json_valid(metadata)),
            result TEXT CHECK(result IS NULL OR json_valid(result)),
            error_code INTEGER,
            error_message TEXT,
            orchestration_state TEXT CHECK(orchestration_state IS NULL OR json_valid(orchestration_state)),
            cancellation_requested_at_ms INTEGER,
            error_type TEXT
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_unified_tasks_user_status ON unified_tasks(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_unified_tasks_owner ON unified_tasks(owner_type, owner_id, status);
        CREATE INDEX IF NOT EXISTS idx_unified_tasks_type_status ON unified_tasks(task_type, status);
        CREATE INDEX IF NOT EXISTS idx_unified_tasks_cancellation ON unified_tasks(cancellation_id);
        CREATE INDEX IF NOT EXISTS idx_unified_tasks_status_updated ON unified_tasks(status, updated_at_ms DESC);
        CREATE INDEX IF NOT EXISTS idx_unified_tasks_recovery
            ON unified_tasks(updated_at_ms)
            WHERE orchestration_state IS NOT NULL
            AND status IN ({active_task_status_check});
        CREATE TABLE IF NOT EXISTS orchestrator_queue_items (
            task_id TEXT PRIMARY KEY REFERENCES unified_tasks(task_id) ON DELETE CASCADE,
            enqueue_seq INTEGER NOT NULL UNIQUE,
            phase TEXT NOT NULL CHECK(phase IN ('ready', 'leased', 'prefetched', 'running', 'dedup_waiting', 'completed', 'failed', 'cancelled')),
            routing_key TEXT NOT NULL,
            plugin_name TEXT,
            available_at_ms INTEGER NOT NULL CHECK(available_at_ms >= {EPOCH_MS_MIN}),
            lease_owner TEXT,
            lease_expires_at_ms INTEGER,
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
            dedup_hash TEXT,
            dedup_lead_task_id TEXT REFERENCES unified_tasks(task_id) ON DELETE SET NULL,
            request_source TEXT NOT NULL,
            delivery_mode TEXT NOT NULL,
            request_priority TEXT NOT NULL CHECK(request_priority IN ('priority', 'standard', 'flex')),
            priority_order_at_ms INTEGER NOT NULL CHECK(priority_order_at_ms >= {EPOCH_MS_MIN}),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            updated_at_ms INTEGER NOT NULL CHECK(updated_at_ms >= {EPOCH_MS_MIN})
        ) STRICT;
        CREATE TABLE IF NOT EXISTS orchestrator_queue_sequence (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            next_enqueue_seq INTEGER NOT NULL
        ) WITHOUT ROWID, STRICT;
        INSERT OR IGNORE INTO orchestrator_queue_sequence (singleton, next_enqueue_seq)
        VALUES (1, 1);
        CREATE TABLE IF NOT EXISTS orchestrator_queue_scheduling_clock (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            last_reserved_at_ms INTEGER NOT NULL CHECK(last_reserved_at_ms >= {EPOCH_MS_MIN})
        ) WITHOUT ROWID, STRICT;
        INSERT OR IGNORE INTO orchestrator_queue_scheduling_clock (
            singleton, last_reserved_at_ms
        ) VALUES (1, {EPOCH_MS_MIN});
        CREATE INDEX IF NOT EXISTS idx_orchestrator_queue_ready
            ON orchestrator_queue_items(phase, request_priority, available_at_ms, priority_order_at_ms, enqueue_seq);
        CREATE INDEX IF NOT EXISTS idx_orchestrator_queue_plugin
            ON orchestrator_queue_items(plugin_name, phase, enqueue_seq);
        CREATE INDEX IF NOT EXISTS idx_orchestrator_queue_lease
            ON orchestrator_queue_items(phase, lease_expires_at_ms);
        CREATE INDEX IF NOT EXISTS idx_orchestrator_queue_dedup
            ON orchestrator_queue_items(dedup_hash, phase);
        """,
    )
