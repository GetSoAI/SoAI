"""SoAI - Plugin backend update schema 3 storage [backend/database/schema_scripts/plugin_backend_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("PLUGIN_BACKEND_UPDATES_SCHEMA_V3",)

PLUGIN_BACKEND_UPDATES_SCHEMA_V3 = """
CREATE TABLE IF NOT EXISTS plugin_backend_updates (
    plugin_name TEXT PRIMARY KEY CHECK(length(trim(plugin_name)) BETWEEN 1 AND 255),
    package_hash TEXT NOT NULL CHECK(length(package_hash) = 64 AND package_hash NOT GLOB '*[^0-9a-f]*'),
    configuration_hash TEXT CHECK(configuration_hash IS NULL OR (length(configuration_hash) = 64 AND configuration_hash NOT GLOB '*[^0-9a-f]*')),
    backend_variant_id TEXT NOT NULL CHECK(length(trim(backend_variant_id)) BETWEEN 1 AND 255),
    status TEXT NOT NULL CHECK(status IN ('check_pending', 'current', 'update_available', 'check_failed')),
    current_version TEXT CHECK(current_version IS NULL OR length(current_version) BETWEEN 1 AND 1024),
    latest_version TEXT CHECK(latest_version IS NULL OR length(latest_version) BETWEEN 1 AND 1024),
    checked_at_ms INTEGER CHECK(checked_at_ms IS NULL OR checked_at_ms >= 0),
    check_id TEXT NOT NULL CHECK(length(trim(check_id)) BETWEEN 1 AND 255),
    failure_code TEXT CHECK(failure_code IS NULL OR length(trim(failure_code)) BETWEEN 1 AND 255),
    auto_request_id TEXT UNIQUE CHECK(auto_request_id IS NULL OR (length(auto_request_id) = 36 AND auto_request_id = lower(auto_request_id))),
    auto_package_hash TEXT CHECK(auto_package_hash IS NULL OR (length(auto_package_hash) = 64 AND auto_package_hash NOT GLOB '*[^0-9a-f]*')),
    auto_configuration_hash TEXT CHECK(auto_configuration_hash IS NULL OR (length(auto_configuration_hash) = 64 AND auto_configuration_hash NOT GLOB '*[^0-9a-f]*')),
    auto_backend_variant_id TEXT CHECK(auto_backend_variant_id IS NULL OR length(trim(auto_backend_variant_id)) BETWEEN 1 AND 255),
    auto_update_failed INTEGER NOT NULL DEFAULT 0 CHECK(auto_update_failed IN (0, 1)),
    CHECK(status NOT IN ('current', 'update_available') OR checked_at_ms IS NOT NULL),
    CHECK((status = 'check_failed') = (failure_code IS NOT NULL)),
    CHECK(
        (auto_request_id IS NULL AND auto_package_hash IS NULL
         AND auto_configuration_hash IS NULL AND auto_backend_variant_id IS NULL
         AND auto_update_failed = 0)
        OR
        (auto_request_id IS NOT NULL AND auto_package_hash IS NOT NULL
         AND auto_backend_variant_id IS NOT NULL)
    )
) STRICT;
CREATE TABLE IF NOT EXISTS plugin_backend_update_network_policy (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    not_before_ms INTEGER CHECK(not_before_ms IS NULL OR not_before_ms >= 0)
) WITHOUT ROWID, STRICT;
INSERT OR IGNORE INTO plugin_backend_update_network_policy(singleton, not_before_ms)
VALUES (1, NULL);
"""
