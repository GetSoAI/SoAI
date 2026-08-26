"""SoAI - Database models parameter operations [backend/database/repositories/models/parameters.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.timing.epoch import epoch_ms
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.json_codec import safe_json_deserialize, safe_json_serialize_value
from database.core.query_execution import (
    query_one_to_dict,
    query_to_dicts,
    sync_fetch_one_as_dict,
)
from database.core.sqlite_numbers import coerce_required_int_from_sqlite_row

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_model_custom_parameters_query",
    "get_parameter_version_query",
    "get_universal_ids_with_custom_parameters_query",
    "sync_increment_parameter_version",
    "sync_update_model_parameters",
)


async def get_parameter_version_query(database: aiosqlite.Connection, universal_id: str) -> int:
    row = await query_one_to_dict(
        database,
        "SELECT parameter_version FROM models_catalog WHERE universal_id = ?",
        (universal_id,),
    )
    if row is None:
        return 0
    return coerce_required_int_from_sqlite_row(row, "parameter_version")


async def get_model_custom_parameters_query(
    database: aiosqlite.Connection,
    universal_id: str,
) -> JSONDict:
    rows = await query_to_dicts(
        database,
        "SELECT param_key, param_value FROM models_parameters WHERE universal_id = ?",
        (universal_id,),
    )
    result: JSONDict = {}
    for row in rows:
        param_key_value = row.get("param_key")
        if isinstance(param_key_value, str):
            raw_value = safe_json_deserialize(row.get("param_value"), None)
            result[param_key_value] = raw_value
    return result


async def get_universal_ids_with_custom_parameters_query(
    database: aiosqlite.Connection,
    universal_ids: list[str],
) -> list[str]:
    if not universal_ids:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for start in range(0, len(universal_ids), SQLITE_BATCH_SIZE):
        batch = [
            universal_id
            for universal_id in universal_ids[start : start + SQLITE_BATCH_SIZE]
            if universal_id
        ]
        if not batch:
            continue
        placeholders = ",".join("?" for _ in batch)
        query = (
            "SELECT DISTINCT universal_id FROM models_parameters "
            f"WHERE universal_id IN ({placeholders})"
        )
        rows = await query_to_dicts(database, query, tuple(batch))
        for row in rows:
            universal_id_value = row.get("universal_id")
            if isinstance(universal_id_value, str) and universal_id_value:
                if universal_id_value not in seen:
                    seen.add(universal_id_value)
                    result.append(universal_id_value)
    return result


def sync_update_model_parameters(
    conn: sqlite3.Connection,
    universal_id: str,
    parameters: JSONDict,
) -> bool:
    conn.execute("DELETE FROM models_parameters WHERE universal_id = ?", (universal_id,))
    if parameters:
        conn.executemany(
            "INSERT INTO models_parameters (universal_id, param_key, param_value) VALUES (?, ?, ?)",
            [
                (
                    universal_id,
                    key,
                    safe_json_serialize_value(
                        value,
                        field_name="param_value",
                        identifier=f"{universal_id}:{key}",
                    ),
                )
                for key, value in parameters.items()
            ],
        )
    return True


def sync_increment_parameter_version(conn: sqlite3.Connection, universal_id: str) -> int:
    conn.execute(
        (
            "UPDATE models_catalog SET parameter_version = parameter_version + 1, "
            "last_modified_at_ms = ? WHERE universal_id = ?"
        ),
        (epoch_ms(), universal_id),
    )
    row = sync_fetch_one_as_dict(
        conn.execute(
            "SELECT parameter_version FROM models_catalog WHERE universal_id = ?",
            (universal_id,),
        ),
    )
    if row is None:
        return -1
    return coerce_required_int_from_sqlite_row(row, "parameter_version")
