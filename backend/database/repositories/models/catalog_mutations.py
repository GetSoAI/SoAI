"""SoAI - Database models catalog write operations [backend/database/repositories/models/catalog_mutations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.timing.epoch import epoch_ms
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.json_codec import safe_json_serialize
from database.core.operations import sync_delete_by_ids
from database.core.query_execution import sync_fetch_all_as_dicts
from database.core.sql_builders import build_update_statement
from database.repositories.models.catalog_upsert import sync_upsert_models

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "sync_delete_models_by_universal_ids",
    "sync_purge_models_for_plugin",
    "sync_set_model_status",
    "sync_set_model_status_for_plugin",
    "sync_update_model_alias",
    "sync_update_model_enabled",
    "sync_update_model_openai_capabilities_overrides",
    "sync_record_model_usage",
    "sync_upsert_models",
)

ALLOWED_MODEL_ALIAS_UPDATE_COLS: frozenset[str] = frozenset(("display_name", "description"))


def sync_purge_models_for_plugin(conn: sqlite3.Connection, plugin_name: str) -> bool:
    universal_ids = [
        universal_id
        for row in sync_fetch_all_as_dicts(
            conn.execute(
                "SELECT universal_id FROM models_catalog WHERE plugin_name = ?",
                (plugin_name,),
            ),
        )
        if isinstance((universal_id := row.get("universal_id")), str)
    ]
    return sync_delete_models_by_universal_ids(conn, universal_ids) > 0


def sync_delete_models_by_universal_ids(conn: sqlite3.Connection, universal_ids: list[str]) -> int:
    return sync_delete_by_ids(conn, "models_catalog", "universal_id", universal_ids)


def sync_set_model_status(conn: sqlite3.Connection, universal_id: str, status: str) -> bool:
    return (
        conn.execute(
            "UPDATE models_catalog SET status = ? WHERE universal_id = ?",
            (status, universal_id),
        ).rowcount
        > 0
    )


def sync_set_model_status_for_plugin(
    conn: sqlite3.Connection,
    plugin_name: str,
    status: str,
) -> tuple[int, list[str]]:
    universal_ids_to_change = [
        universal_id
        for row in sync_fetch_all_as_dicts(
            conn.execute(
                "SELECT universal_id FROM models_catalog WHERE plugin_name = ? AND status != ?",
                (plugin_name, status),
            ),
        )
        if isinstance((universal_id := row.get("universal_id")), str)
    ]
    if not universal_ids_to_change:
        return (0, [])
    for start in range(0, len(universal_ids_to_change), SQLITE_BATCH_SIZE):
        batch = universal_ids_to_change[start : start + SQLITE_BATCH_SIZE]
        placeholders = ",".join("?" for _ in batch)
        conn.execute(
            f"UPDATE models_catalog SET status = ? WHERE universal_id IN ({placeholders})",
            [status] + batch,
        )
    return (len(universal_ids_to_change), universal_ids_to_change)


def sync_update_model_alias(conn: sqlite3.Connection, universal_id: str, updates: JSONDict) -> bool:
    if not updates:
        return True
    invalid_cols = set(updates.keys()) - ALLOWED_MODEL_ALIAS_UPDATE_COLS
    if invalid_cols:
        raise ValidationError(f"Invalid column names for model alias update: {invalid_cols}")
    updates_sql: dict[str, SQLiteValue] = {}
    if "display_name" in updates:
        display_name = updates.get("display_name")
        if display_name is None:
            updates_sql["display_name"] = None
        elif isinstance(display_name, str):
            updates_sql["display_name"] = display_name
        else:
            raise ValidationError("display_name must be a string or null.")
    if "description" in updates:
        description = updates.get("description")
        if description is None:
            updates_sql["description"] = None
        elif isinstance(description, str):
            updates_sql["description"] = description
        else:
            raise ValidationError("description must be a string or null.")
    updates_sql["last_modified_at_ms"] = epoch_ms()
    sql, params = build_update_statement(
        table="models_catalog",
        updates=updates_sql,
        where_clause="universal_id = ?",
        where_params=(universal_id,),
        allowed_columns=ALLOWED_MODEL_ALIAS_UPDATE_COLS | {"last_modified_at_ms"},
    )
    return conn.execute(sql, params).rowcount > 0


def sync_record_model_usage(
    conn: sqlite3.Connection,
    universal_id: str,
    plugin_name: str,
) -> tuple[int, int] | None:
    model_row = conn.execute(
        "SELECT plugin_name FROM models_catalog WHERE universal_id = ?",
        (universal_id,),
    ).fetchone()
    if model_row is None or model_row[0] != plugin_name:
        return None
    plugin_row = conn.execute(
        "SELECT plugin_name FROM plugins_catalog WHERE plugin_name = ?",
        (plugin_name,),
    ).fetchone()
    if plugin_row is None:
        raise StateError(
            "Model usage references a missing plugin catalog record.",
            operation="database.models.record_model_usage",
            details={"universal_id": universal_id, "plugin_name": plugin_name},
        )
    model_revision_row = conn.execute(
        "SELECT last_used_revision FROM models_catalog WHERE last_used_revision > 0 ORDER BY last_used_revision DESC LIMIT 1",
    ).fetchone()
    plugin_revision_row = conn.execute(
        "SELECT last_used_revision FROM plugins_catalog WHERE last_used_revision > 0 ORDER BY last_used_revision DESC LIMIT 1",
    ).fetchone()
    model_revision = int(model_revision_row[0]) if model_revision_row is not None else 0
    plugin_revision = int(plugin_revision_row[0]) if plugin_revision_row is not None else 0
    revision = max(model_revision, plugin_revision) + 1
    now = epoch_ms()
    model_count = conn.execute(
        "UPDATE models_catalog SET request_count = request_count + 1, last_used_at_ms = ?, last_used_revision = ? WHERE universal_id = ? AND plugin_name = ?",
        (now, revision, universal_id, plugin_name),
    ).rowcount
    if model_count != 1:
        raise StateError(
            "Model usage update violated the validated model invariant.",
            operation="database.models.record_model_usage",
            details={"universal_id": universal_id, "plugin_name": plugin_name},
        )
    plugin_count = conn.execute(
        "UPDATE plugins_catalog SET last_used_at_ms = ?, last_used_revision = ? WHERE plugin_name = ?",
        (now, revision, plugin_name),
    ).rowcount
    if plugin_count != 1:
        raise StateError(
            "Plugin usage update violated the validated plugin invariant.",
            operation="database.models.record_model_usage",
            details={"universal_id": universal_id, "plugin_name": plugin_name},
        )
    return (now, revision)


def sync_update_model_openai_capabilities_overrides(
    conn: sqlite3.Connection,
    universal_id: str,
    overrides: JSONDict | None,
) -> bool:
    normalized: JSONDict | None = dict(overrides) if isinstance(overrides, dict) else None
    if normalized is not None and not normalized:
        normalized = None
    payload = safe_json_serialize(
        normalized,
        "openai_capabilities_overrides",
        universal_id,
    )
    updates_sql: dict[str, SQLiteValue] = {
        "openai_capabilities_overrides": payload,
        "last_modified_at_ms": epoch_ms(),
    }
    sql, params = build_update_statement(
        table="models_catalog",
        updates=updates_sql,
        where_clause="universal_id = ?",
        where_params=(universal_id,),
        allowed_columns=frozenset({"openai_capabilities_overrides", "last_modified_at_ms"}),
    )
    return conn.execute(sql, params).rowcount > 0


def sync_update_model_enabled(
    conn: sqlite3.Connection,
    universal_id: str,
    enabled: bool,
) -> bool:
    updates_sql: dict[str, SQLiteValue] = {
        "is_enabled": 1 if enabled else 0,
        "last_modified_at_ms": epoch_ms(),
    }
    sql, params = build_update_statement(
        table="models_catalog",
        updates=updates_sql,
        where_clause="universal_id = ?",
        where_params=(universal_id,),
        allowed_columns=frozenset({"is_enabled", "last_modified_at_ms"}),
    )
    return conn.execute(sql, params).rowcount > 0
