"""SoAI - Plugin backend variant persistence [backend/database/repositories/plugins/backend_variants.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.plugins.backend_variant_ids import (
    AUTO_BACKEND_VARIANT_ID,
    require_backend_variant_id,
)
from core.timing.epoch import epoch_ms
from core.validation.strict_numbers import require_non_negative_int_strict
from database.core.query_execution import query_to_dicts

__all__ = (
    "get_backend_variant_id_query",
    "sync_set_backend_variant_id",
    "sync_update_backend_variant_available_count",
)


async def get_backend_variant_id_query(
    database: aiosqlite.Connection,
    plugin_name: str,
) -> str | None:
    rows = await query_to_dicts(
        database,
        "SELECT backend_variant_id FROM plugins_catalog WHERE plugin_name = ?",
        (plugin_name,),
    )
    if not rows:
        return None
    value = rows[0].get("backend_variant_id")
    if isinstance(value, str) and value.strip():
        return require_backend_variant_id(value)
    return AUTO_BACKEND_VARIANT_ID


def sync_set_backend_variant_id(
    conn: sqlite3.Connection,
    plugin_name: str,
    backend_variant_id: str,
) -> None:
    variant_id = require_backend_variant_id(backend_variant_id)
    conn.execute(
        "UPDATE plugins_catalog SET backend_variant_id = ?, last_seen_at_ms = ? WHERE plugin_name = ?",
        (variant_id, epoch_ms(), plugin_name),
    )


def sync_update_backend_variant_available_count(
    conn: sqlite3.Connection,
    plugin_name: str,
    expected_state: str,
    available_count: int,
) -> bool:
    normalized_count = require_non_negative_int_strict(
        available_count,
        error_message="Backend variant available count must be a non-negative integer.",
    )
    now = epoch_ms()
    existing_cursor = conn.execute(
        (
            "SELECT backend_variant_available_count FROM plugins_catalog "
            "WHERE plugin_name = ? AND state = ? AND supports_backend_installation = 1"
        ),
        (plugin_name, expected_state),
    )
    existing_row = existing_cursor.fetchone()
    if existing_row is None:
        return False
    existing_count = existing_row[0]
    count_changed = not isinstance(existing_count, int) or existing_count != normalized_count
    conn.execute(
        (
            "UPDATE plugins_catalog "
            "SET backend_variant_available_count = ?, backend_variant_count_updated_at_ms = ?, last_seen_at_ms = ? "
            "WHERE plugin_name = ? AND state = ? AND supports_backend_installation = 1"
        ),
        (normalized_count, now, now, plugin_name, expected_state),
    )
    return count_changed
