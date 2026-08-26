"""SoAI - Database speed test operations [backend/database/repositories/hardware/speed.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

import aiosqlite

from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.core.sqlite_numbers import (
    coerce_float_from_sqlite,
    coerce_float_value_from_sqlite,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "SpeedTestWritePayload",
    "get_latest_network_speed_snapshot_query",
    "get_latest_speed_test_snapshot_query",
    "get_median_real_download_speed_query",
    "get_speed_test_query",
    "sync_insert_real_download_speed",
    "sync_upsert_speed_test",
)


@dataclass(frozen=True, slots=True)
class SpeedTestWritePayload:
    cache_key: str
    path: str
    sample_bytes: int
    observed_at_ms: int
    duration_ms: int
    bytes_processed: int
    bytes_per_second: float


async def get_latest_network_speed_snapshot_query(
    database: aiosqlite.Connection,
) -> JSONDict:
    query = "SELECT h.device_id, h.interface, h.upload_mbps, h.download_mbps, h.observed_at_ms FROM hardware_network_history h JOIN (SELECT device_id, MAX(observed_at_ms) AS ts FROM hardware_network_history GROUP BY device_id) latest ON latest.device_id = h.device_id AND latest.ts = h.observed_at_ms"
    rows = await query_to_dicts(database, query)
    result: JSONDict = {}
    for row in rows:
        if device_id := row.get("device_id"):
            result[str(device_id)] = {
                "interface": row.get("interface"),
                "upload_mbps": coerce_float_from_sqlite(row.get("upload_mbps")),
                "download_mbps": coerce_float_from_sqlite(row.get("download_mbps")),
                "observed_at_ms": coerce_float_from_sqlite(row.get("observed_at_ms")),
            }
    return result


async def get_latest_speed_test_snapshot_query(
    database: aiosqlite.Connection,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        "SELECT cache_key, path, sample_bytes, observed_at_ms, duration_ms, bytes_processed, bytes_per_second FROM system_speed_tests ORDER BY observed_at_ms DESC LIMIT 1",
    )
    if row is None:
        return None
    return sqlite_row_dict_to_json_dict(row)


def sync_upsert_speed_test(
    conn: sqlite3.Connection,
    payload: SpeedTestWritePayload,
) -> None:
    conn.execute(
        "INSERT INTO system_speed_tests (cache_key, path, sample_bytes, observed_at_ms, duration_ms, bytes_processed, bytes_per_second) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(cache_key) DO UPDATE SET path=excluded.path, sample_bytes=excluded.sample_bytes, observed_at_ms=excluded.observed_at_ms, duration_ms=excluded.duration_ms, bytes_processed=excluded.bytes_processed, bytes_per_second=excluded.bytes_per_second",
        (
            payload.cache_key,
            payload.path,
            payload.sample_bytes,
            payload.observed_at_ms,
            payload.duration_ms,
            payload.bytes_processed,
            payload.bytes_per_second,
        ),
    )


async def get_speed_test_query(
    database: aiosqlite.Connection,
    cache_key: str,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        "SELECT cache_key, path, sample_bytes, observed_at_ms, duration_ms, bytes_processed, bytes_per_second FROM system_speed_tests WHERE cache_key = ?",
        (cache_key,),
    )
    if row is None:
        return None
    return sqlite_row_dict_to_json_dict(row)


def sync_insert_real_download_speed(
    conn: sqlite3.Connection,
    plugin_name: str,
    model_id: str,
    bytes_downloaded: int,
    duration_ms: int,
    bytes_per_second: float,
    observed_at_ms: int,
) -> None:
    conn.execute(
        "INSERT INTO real_download_speeds (plugin_name, model_id, bytes_downloaded, duration_ms, bytes_per_second, observed_at_ms) VALUES (?, ?, ?, ?, ?, ?)",
        (
            plugin_name,
            model_id,
            bytes_downloaded,
            duration_ms,
            bytes_per_second,
            observed_at_ms,
        ),
    )


async def get_median_real_download_speed_query(
    database: aiosqlite.Connection,
) -> JSONDict | None:
    rows = await query_to_dicts(
        database,
        "SELECT bytes_per_second, observed_at_ms FROM real_download_speeds ORDER BY observed_at_ms DESC LIMIT 10",
    )
    if not rows:
        return None
    speeds = sorted(coerce_float_value_from_sqlite(row.get("bytes_per_second")) for row in rows)
    sample_count = len(speeds)
    median_speed = (
        speeds[sample_count // 2]
        if sample_count % 2 == 1
        else (speeds[sample_count // 2 - 1] + speeds[sample_count // 2]) / 2
    )
    latest_observed_ms = max(
        coerce_float_value_from_sqlite(row.get("observed_at_ms")) for row in rows
    )
    return {
        "bytes_per_second": median_speed,
        "observed_at_ms": latest_observed_ms,
        "sample_count": sample_count,
        "source": "real_download",
    }
