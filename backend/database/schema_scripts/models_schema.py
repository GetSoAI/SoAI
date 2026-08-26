"""SoAI - Database schema: model catalog tables [backend/database/schema_scripts/models_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script

__all__ = ("apply_models_schema",)


def _build_models_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS models_external_providers (
            id TEXT PRIMARY KEY, plugin_name TEXT NOT NULL, name TEXT, canonical_name TEXT, api_url TEXT NOT NULL, api_key TEXT,
            models_filter TEXT CHECK(models_filter IS NULL OR json_valid(models_filter)),
            context_window_tokens INTEGER CHECK(context_window_tokens IS NULL OR context_window_tokens > 0),
            extra_headers TEXT CHECK(extra_headers IS NULL OR json_valid(extra_headers)),
            extra_query_params TEXT CHECK(extra_query_params IS NULL OR json_valid(extra_query_params)),
            last_status TEXT DEFAULT 'UNCHECKED' CHECK(last_status IN ('UNCHECKED', 'OK', 'ERROR', 'TIMEOUT', 'VALIDATING', 'AUTH_REQUIRED')),
            last_error TEXT,
            last_checked_at_ms INTEGER,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
            CHECK((name IS NULL) = (canonical_name IS NULL)),
            UNIQUE (plugin_name, api_url),
            FOREIGN KEY(plugin_name) REFERENCES plugins_catalog(plugin_name) ON DELETE CASCADE
        ) STRICT;
        CREATE UNIQUE INDEX IF NOT EXISTS uidx_external_provider_canonical_name
        ON models_external_providers(plugin_name, canonical_name)
        WHERE canonical_name IS NOT NULL;
        CREATE TABLE IF NOT EXISTS models_catalog (
            universal_id TEXT PRIMARY KEY,
            plugin_name TEXT NOT NULL,
            model_id TEXT NOT NULL,
            source_model_id TEXT NOT NULL,
            display_name TEXT,
            description TEXT,
            content_hash TEXT,
            file_path TEXT,
            size_bytes INTEGER,
            file_modified_at_ms INTEGER,
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            last_discovered_at_ms INTEGER,
            last_modified_at_ms INTEGER,
            last_used_at_ms INTEGER,
            last_used_revision INTEGER NOT NULL DEFAULT 0 CHECK(last_used_revision >= 0),
            request_count INTEGER NOT NULL DEFAULT 0,
            context_window_tokens INTEGER CHECK(context_window_tokens IS NULL OR context_window_tokens > 0),
            raw_details TEXT CHECK(raw_details IS NULL OR json_valid(raw_details)),
            parameter_version INTEGER NOT NULL DEFAULT 0,
            provider_id TEXT, status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'inactive_plugin_error')),
            is_enabled INTEGER NOT NULL DEFAULT 1 CHECK(is_enabled IN (0, 1)),
            capabilities TEXT CHECK(capabilities IS NULL OR json_valid(capabilities)),
            openai_capabilities_overrides TEXT CHECK(openai_capabilities_overrides IS NULL OR json_valid(openai_capabilities_overrides)),
            tags TEXT CHECK(tags IS NULL OR json_valid(tags)),
            family TEXT, license TEXT, quantization TEXT,
            FOREIGN KEY(plugin_name) REFERENCES plugins_catalog(plugin_name) ON DELETE CASCADE,
            FOREIGN KEY(provider_id) REFERENCES models_external_providers(id) ON DELETE SET NULL
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_models_plugin ON models_catalog(plugin_name);
        CREATE INDEX IF NOT EXISTS idx_models_provider_id ON models_catalog(provider_id);
        CREATE INDEX IF NOT EXISTS idx_models_universal_id_lower ON models_catalog(lower(universal_id));
        CREATE INDEX IF NOT EXISTS idx_models_display_name_lower ON models_catalog(lower(display_name));
        CREATE INDEX IF NOT EXISTS idx_models_source_model_id_lower ON models_catalog(lower(source_model_id));
        CREATE INDEX IF NOT EXISTS idx_models_model_id_lower ON models_catalog(lower(model_id));
        CREATE INDEX IF NOT EXISTS idx_models_model_id ON models_catalog(model_id);
        CREATE INDEX IF NOT EXISTS idx_models_source_model_id ON models_catalog(source_model_id);
        CREATE INDEX IF NOT EXISTS idx_models_last_used_revision
        ON models_catalog(last_used_revision DESC)
        WHERE last_used_revision > 0;
        CREATE UNIQUE INDEX IF NOT EXISTS uidx_models_unique_source_model_id ON models_catalog(plugin_name, ifnull(provider_id, ''), source_model_id);
        CREATE UNIQUE INDEX IF NOT EXISTS uidx_models_unique_model_id ON models_catalog(plugin_name, ifnull(provider_id, ''), model_id);
        CREATE TABLE IF NOT EXISTS models_parameters (
            universal_id TEXT NOT NULL, param_key TEXT NOT NULL,
            param_value TEXT CHECK(param_value IS NULL OR json_valid(param_value)),
            PRIMARY KEY (universal_id, param_key),
            FOREIGN KEY(universal_id) REFERENCES models_catalog(universal_id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        CREATE TABLE IF NOT EXISTS models_virtual_models (
            name TEXT PRIMARY KEY, strategy TEXT NOT NULL,
            is_enabled INTEGER NOT NULL DEFAULT 1 CHECK(is_enabled IN (0, 1)),
            created_at_ms INTEGER NOT NULL CHECK(created_at_ms >= {EPOCH_MS_MIN}),
            last_modified_at_ms INTEGER NOT NULL CHECK(last_modified_at_ms >= {EPOCH_MS_MIN})
        ) STRICT;
        CREATE TABLE IF NOT EXISTS models_virtual_model_members (
            virtual_model_name TEXT NOT NULL,
            universal_id TEXT NOT NULL,
            position INTEGER NOT NULL,
            parameters TEXT CHECK(parameters IS NULL OR json_valid(parameters)),
            PRIMARY KEY (virtual_model_name, universal_id),
            FOREIGN KEY(virtual_model_name) REFERENCES models_virtual_models(name) ON DELETE CASCADE,
            FOREIGN KEY(universal_id) REFERENCES models_catalog(universal_id) ON DELETE CASCADE
        ) WITHOUT ROWID, STRICT;
        CREATE INDEX IF NOT EXISTS idx_virtual_model_members_model ON models_virtual_model_members(universal_id);
        CREATE TABLE IF NOT EXISTS models_circuit_breakers (
            plugin_name TEXT PRIMARY KEY,
            state TEXT NOT NULL CHECK(state IN ('closed', 'open', 'half-open')),
            failure_count INTEGER NOT NULL,
            last_failure_at_ms INTEGER NOT NULL CHECK(last_failure_at_ms >= 0),
            FOREIGN KEY(plugin_name) REFERENCES plugins_catalog(plugin_name) ON DELETE CASCADE
        ) STRICT;
        CREATE TABLE IF NOT EXISTS provider_mutation_outcomes (
            operation_id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            operation_type TEXT NOT NULL CHECK(operation_type IN ('create', 'update', 'delete')),
            plugin_name TEXT NOT NULL,
            provider_id TEXT NOT NULL,
            expected_revision INTEGER NOT NULL CHECK(expected_revision >= 0),
            request_digest TEXT NOT NULL CHECK(length(request_digest) = 64),
            outcome TEXT NOT NULL CHECK(outcome IN ('created', 'updated', 'deleted', 'conflict', 'stale_revision', 'not_found')),
            provider_revision INTEGER CHECK(provider_revision IS NULL OR provider_revision >= 0),
            provider_json TEXT CHECK(provider_json IS NULL OR (json_valid(provider_json) AND json_type(provider_json) = 'object')),
            accepted_at_ms INTEGER NOT NULL,
            expires_at_ms INTEGER NOT NULL CHECK(expires_at_ms > accepted_at_ms)
        ) STRICT;
        CREATE TABLE IF NOT EXISTS provider_mutation_clock (
            singleton_id INTEGER PRIMARY KEY CHECK(singleton_id = 1),
            server_time_watermark_ms INTEGER NOT NULL CHECK(server_time_watermark_ms >= 0)
        ) STRICT;
"""


def apply_models_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, _build_models_schema_sql())
