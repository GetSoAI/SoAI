"""SoAI - Plugin catalog schema ownership [backend/database/schema_scripts/plugin_catalog_schema.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.validation.epoch import EPOCH_MS_MIN
from database.sql.script import execute_sql_script


def build_plugin_catalog_schema_sql() -> str:
    return f"""
        CREATE TABLE IF NOT EXISTS plugins_catalog (
            plugin_name TEXT PRIMARY KEY, name TEXT, description_soaiplugin TEXT, website_soaiplugin TEXT, author_soaiplugin TEXT, version_soaiplugin TEXT,
            license_soaiplugin TEXT, license_managed_backend TEXT,
            core_compat TEXT,
            aliases TEXT CHECK(aliases IS NULL OR json_valid(aliases)),
            dependencies TEXT CHECK(dependencies IS NULL OR json_valid(dependencies)),
            modalities TEXT CHECK(modalities IS NULL OR json_valid(modalities)),
            file_path TEXT, file_hash TEXT,
            backend_variant_id TEXT NOT NULL DEFAULT 'auto',
            backend_variant_available_count INTEGER CHECK(backend_variant_available_count IS NULL OR backend_variant_available_count >= 0),
            backend_variant_count_updated_at_ms INTEGER CHECK(backend_variant_count_updated_at_ms IS NULL OR backend_variant_count_updated_at_ms >= {EPOCH_MS_MIN}),
            supports_backend_installation INTEGER NOT NULL CHECK(supports_backend_installation IN (0, 1)),
            supports_backend_process_tracking INTEGER NOT NULL DEFAULT 0 CHECK(supports_backend_process_tracking IN (0, 1)),
            runtime_processes TEXT CHECK(runtime_processes IS NULL OR json_valid(runtime_processes)),
            runtime_processes_updated_at_ms INTEGER,
            supports_model_deletion INTEGER NOT NULL DEFAULT 0 CHECK(supports_model_deletion IN (0, 1)),
            supports_model_download INTEGER NOT NULL CHECK(supports_model_download IN (0, 1)),
            has_configuration INTEGER NOT NULL CHECK(has_configuration IN (0, 1)),
            supports_gpu_binding INTEGER NOT NULL DEFAULT 0 CHECK(supports_gpu_binding IN (0, 1)),
            supports_external_providers INTEGER NOT NULL CHECK(supports_external_providers IN (0, 1)),
            external_provider_mode TEXT NOT NULL DEFAULT 'none'
                CHECK(external_provider_mode IN ('none', 'user_managed', 'plugin_managed')),
            external_provider_defaults TEXT CHECK(external_provider_defaults IS NULL OR json_valid(external_provider_defaults)),
            persistent INTEGER NOT NULL DEFAULT 0 CHECK(persistent IN (0, 1)), max_concurrent_requests INTEGER,
            local_resources INTEGER NOT NULL DEFAULT 0 CHECK(local_resources IN (0, 1)), local_models INTEGER NOT NULL DEFAULT 0 CHECK(local_models IN (0, 1)),
            supports_cloning INTEGER NOT NULL DEFAULT 0 CHECK(supports_cloning IN (0, 1)),
            state TEXT NOT NULL DEFAULT 'NOT_DETECTED' CHECK(state IN ('ACTIVATING', 'NOT_DETECTED', 'BACKEND_NOT_INSTALLED', 'BACKEND_INSTALLING', 'BACKEND_UPDATING', 'STOPPED', 'REMOVING_BACKEND', 'DELETING', 'INSTALL_ERROR', 'LOAD_ERROR', 'UPDATE_ERROR', 'BACKEND_UNINSTALL_ERROR', 'DELETE_ERROR', 'PERSISTENT_READY', 'ABSENT', 'INCOMPATIBLE', 'UNKNOWN', 'STARTING', 'LOADING', 'IDLE', 'READY_PENDING_DISPATCH', 'READY', 'READY_DIRTY', 'PROCESSING', 'STOPPING', 'ERROR', 'QUARANTINED', 'DISABLED')), welcome_message_logged INTEGER NOT NULL DEFAULT 0 CHECK(welcome_message_logged IN (0, 1)),
            first_seen_at_ms INTEGER NOT NULL CHECK(first_seen_at_ms >= {EPOCH_MS_MIN}),
            last_seen_at_ms INTEGER NOT NULL CHECK(last_seen_at_ms >= {EPOCH_MS_MIN}),
            last_used_at_ms INTEGER,
            last_used_revision INTEGER NOT NULL DEFAULT 0 CHECK(last_used_revision >= 0),
            model_repository TEXT,
            model_types TEXT CHECK(model_types IS NULL OR json_valid(model_types)),
            website_backend TEXT,
            required_system_capabilities TEXT CHECK(required_system_capabilities IS NULL OR json_valid(required_system_capabilities)),
            openai_capabilities TEXT CHECK(openai_capabilities IS NULL OR json_valid(openai_capabilities)),
            user_enabled_once INTEGER NOT NULL DEFAULT 0 CHECK(user_enabled_once IN (0, 1)), incompatibility_reason TEXT,
            incompatibility_override INTEGER NOT NULL DEFAULT 0 CHECK(incompatibility_override IN (0, 1)),
            incompatibility_details TEXT CHECK(incompatibility_details IS NULL OR json_valid(incompatibility_details)),
            incompatibility_message TEXT,
            default_configuration TEXT CHECK(default_configuration IS NULL OR json_valid(default_configuration)),
            parameter_schema TEXT CHECK(parameter_schema IS NULL OR json_valid(parameter_schema)),
            backend_variant_options TEXT CHECK(backend_variant_options IS NULL OR json_valid(backend_variant_options)),
            supports_model_search INTEGER NOT NULL DEFAULT 0 CHECK(supports_model_search IN (0, 1)),
            supports_model_variant_discovery INTEGER NOT NULL DEFAULT 0 CHECK(supports_model_variant_discovery IN (0, 1)),
            runtime_loaded INTEGER NOT NULL DEFAULT 0 CHECK(runtime_loaded IN (0, 1)),
            backend_status TEXT CHECK(backend_status IS NULL OR json_valid(backend_status)),
            catalog_reconciled_at_ms INTEGER CHECK(catalog_reconciled_at_ms IS NULL OR catalog_reconciled_at_ms >= {EPOCH_MS_MIN})
        ) STRICT;
        CREATE INDEX IF NOT EXISTS idx_plugin_state ON plugins_catalog (state);
        CREATE INDEX IF NOT EXISTS idx_plugins_last_used_revision
        ON plugins_catalog(last_used_revision DESC)
        WHERE last_used_revision > 0;
    """


def apply_plugin_catalog_schema(conn: sqlite3.Connection) -> None:
    execute_sql_script(conn, build_plugin_catalog_schema_sql())


__all__ = ("apply_plugin_catalog_schema", "build_plugin_catalog_schema_sql")
