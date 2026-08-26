"""SoAI - Database genesis metrics operations [backend/database/repositories/metrics/genesis.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.validation.coercion import coerce_int_strict
from database.core.json_codec import safe_json_deserialize
from database.core.query_execution import query_to_dicts, sync_fetch_one_as_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_genesis_data_query",
    "sync_increment_genesis_counters",
    "sync_initialize_genesis",
    "sync_reset_genesis_counters",
    "sync_reset_genesis_uptime",
    "sync_update_genesis_uptime",
)

GENESIS_KEYS: tuple[str, ...] = (
    "genesis.uptime_ms",
    "genesis.requests_total",
    "genesis.tokens_total",
    "genesis.first_startup_ts_ms",
)


async def get_genesis_data_query(
    database: aiosqlite.Connection,
) -> JSONDict:
    rows = await query_to_dicts(
        database,
        "SELECT key, value FROM webui_system_settings WHERE key IN (?, ?, ?, ?)",
        GENESIS_KEYS,
    )
    result: JSONDict = {
        "uptime_ms": 0,
        "requests_total": 0,
        "tokens_total": 0,
        "first_startup_ts_ms": 0,
    }
    for row in rows:
        key = row.get("key")
        raw_value = row.get("value")
        value = safe_json_deserialize(raw_value, None)
        if key == "genesis.uptime_ms":
            result["uptime_ms"] = coerce_int_strict(value)
        elif key == "genesis.requests_total":
            result["requests_total"] = coerce_int_strict(value)
        elif key == "genesis.tokens_total":
            result["tokens_total"] = coerce_int_strict(value)
        elif key == "genesis.first_startup_ts_ms":
            result["first_startup_ts_ms"] = coerce_int_strict(value)
    return result


def sync_update_genesis_uptime(
    conn: sqlite3.Connection,
    delta_ms: int,
) -> None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT value FROM webui_system_settings WHERE key = ?",
            ("genesis.uptime_ms",),
        ),
    )
    current_uptime = 0
    value = row.get("value") if row else None
    if value is not None:
        parsed_value = safe_json_deserialize(value, 0)
        current_uptime = coerce_int_strict(parsed_value)
    new_uptime = current_uptime + int(delta_ms)
    conn.execute(
        "INSERT INTO webui_system_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        ("genesis.uptime_ms", serialize_json_compact_stable_strict(new_uptime)),
    )


def sync_increment_genesis_counters(
    conn: sqlite3.Connection,
    requests_delta: int,
    tokens_delta: int,
) -> None:
    for key, delta in (
        ("genesis.requests_total", requests_delta),
        ("genesis.tokens_total", tokens_delta),
    ):
        if delta <= 0:
            continue
        row = sync_fetch_one_as_dict(
            conn.execute("SELECT value FROM webui_system_settings WHERE key = ?", (key,)),
        )
        current_value = 0
        value = row.get("value") if row else None
        if value is not None:
            parsed_value = safe_json_deserialize(value, 0)
            current_value = coerce_int_strict(parsed_value)
        new_value = current_value + delta
        conn.execute(
            "INSERT INTO webui_system_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, serialize_json_compact_stable_strict(new_value)),
        )


def sync_reset_genesis_counters(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO webui_system_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        [
            ("genesis.requests_total", serialize_json_compact_stable_strict(0)),
            ("genesis.tokens_total", serialize_json_compact_stable_strict(0)),
        ],
    )


def sync_reset_genesis_uptime(conn: sqlite3.Connection) -> None:
    now = epoch_ms()
    conn.executemany(
        "INSERT INTO webui_system_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        [
            ("genesis.uptime_ms", serialize_json_compact_stable_strict(0)),
            ("genesis.first_startup_ts_ms", serialize_json_compact_stable_strict(now)),
        ],
    )


def sync_initialize_genesis(
    conn: sqlite3.Connection,
    now_ts_ms: int,
) -> None:
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT key FROM webui_system_settings WHERE key = ?",
            ("genesis.first_startup_ts_ms",),
        ),
    )
    if row is None:
        genesis_defaults = [
            ("genesis.uptime_ms", serialize_json_compact_stable_strict(0)),
            ("genesis.requests_total", serialize_json_compact_stable_strict(0)),
            ("genesis.tokens_total", serialize_json_compact_stable_strict(0)),
            ("genesis.first_startup_ts_ms", serialize_json_compact_stable_strict(int(now_ts_ms))),
        ]
        conn.executemany(
            "INSERT INTO webui_system_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
            genesis_defaults,
        )
