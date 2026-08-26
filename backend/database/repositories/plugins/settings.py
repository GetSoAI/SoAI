"""SoAI - Database plugins system settings and circuit breaker [backend/database/repositories/plugins/settings.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.plugins.protocols_database import CircuitBreakerStatePayload
from core.serialization.json import serialize_json_compact_stable_strict
from database.core.json_codec import safe_json_deserialize
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.row_formatting import format_row

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "get_all_circuit_breaker_states_query",
    "get_system_setting_query",
    "sync_set_system_setting",
    "sync_upsert_circuit_breaker_state",
)


async def get_system_setting_query(database: aiosqlite.Connection, key: str) -> JSONValue | None:
    row = await query_one_to_dict(
        database,
        "SELECT value FROM webui_system_settings WHERE key = ?",
        (key,),
    )
    if row is None:
        return None
    value = row.get("value")
    if value is None:
        return None
    return safe_json_deserialize(value, None)


def sync_set_system_setting(conn: sqlite3.Connection, key: str, value: JSONValue) -> None:
    json_value = serialize_json_compact_stable_strict(value)
    conn.execute(
        "INSERT INTO webui_system_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, json_value),
    )


async def get_all_circuit_breaker_states_query(
    database: aiosqlite.Connection,
) -> list[JSONDict]:
    rows = await query_to_dicts(database, "SELECT * FROM models_circuit_breakers")
    return [formatted for row in rows if (formatted := format_row(row))]


def sync_upsert_circuit_breaker_state(
    conn: sqlite3.Connection,
    plugin_name: str,
    state: CircuitBreakerStatePayload,
) -> None:
    params = (
        plugin_name,
        state["state"].value,
        state["failure_count"],
        state["last_failure_at_ms"],
    )
    conn.execute(
        "INSERT INTO models_circuit_breakers (plugin_name, state, failure_count, last_failure_at_ms) VALUES (?, ?, ?, ?) ON CONFLICT(plugin_name) DO UPDATE SET state=excluded.state, failure_count=excluded.failure_count, last_failure_at_ms=excluded.last_failure_at_ms",
        params,
    )
