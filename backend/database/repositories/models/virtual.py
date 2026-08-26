"""SoAI - Database virtual models operations [backend/database/repositories/models/virtual.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.orchestrator.routing_config import ConstituentModelConfig, VirtualModelConfig
from core.serialization.json import serialize_json_compact_stable_strict
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.json_codec import safe_json_deserialize
from database.core.query_execution import query_to_dicts
from database.core.sqlite_numbers import (
    coerce_required_int_from_sqlite_row,
    coerce_required_nonempty_str_from_sqlite_row,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "find_virtual_models_using_universal_ids_query",
    "get_virtual_model_query",
    "list_all_virtual_models_query",
    "row_to_virtual_model",
    "sync_add_or_update_virtual_model",
    "sync_delete_virtual_model",
)


def row_to_virtual_model(row: SQLiteRowDict, members: list[SQLiteRowDict]) -> VirtualModelConfig:
    def _position_key(entry: SQLiteRowDict) -> int:
        return coerce_required_int_from_sqlite_row(entry, "position")

    models = [
        ConstituentModelConfig(
            universal_id=str(member["universal_id"]),
            parameters=_require_parameters(
                safe_json_deserialize(member.get("parameters"), None),
                virtual_model_name=str(row.get("name") or ""),
                universal_id=str(member.get("universal_id") or ""),
            ),
        )
        for member in sorted(members, key=_position_key)
    ]
    return VirtualModelConfig(
        name=coerce_required_nonempty_str_from_sqlite_row(row, "name"),
        strategy=coerce_required_nonempty_str_from_sqlite_row(row, "strategy"),
        models=models,
        created_at_ms=coerce_required_int_from_sqlite_row(row, "created_at_ms"),
        last_modified_at_ms=coerce_required_int_from_sqlite_row(row, "last_modified_at_ms"),
        is_enabled=coerce_required_int_from_sqlite_row(row, "is_enabled") != 0,
    )


def _require_parameters(
    value: JSONValue | None,
    *,
    virtual_model_name: str,
    universal_id: str,
) -> dict[str, JSONValue]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValidationError(
            "Virtual model member parameters must be a JSON object or null.",
            details={"virtual_model_name": virtual_model_name, "universal_id": universal_id},
        )
    result: dict[str, JSONValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValidationError(
                "Virtual model member parameters keys must be strings.",
                details={"virtual_model_name": virtual_model_name, "universal_id": universal_id},
            )
        result[key] = item
    return result


def sync_add_or_update_virtual_model(
    conn: sqlite3.Connection,
    virtual_model: VirtualModelConfig,
) -> None:
    params = (
        virtual_model.name,
        virtual_model.strategy,
        1 if virtual_model.is_enabled else 0,
        virtual_model.created_at_ms,
        virtual_model.last_modified_at_ms,
    )
    conn.execute(
        "INSERT INTO models_virtual_models (name, strategy, is_enabled, created_at_ms, last_modified_at_ms) VALUES (?, ?, ?, ?, ?) ON CONFLICT(name) DO UPDATE SET strategy=excluded.strategy, is_enabled=excluded.is_enabled, last_modified_at_ms=excluded.last_modified_at_ms",
        params,
    )
    conn.execute(
        "DELETE FROM models_virtual_model_members WHERE virtual_model_name = ?",
        (virtual_model.name,),
    )
    for position, model in enumerate(virtual_model.models):
        params_member = (
            virtual_model.name,
            model.universal_id,
            position,
            serialize_json_compact_stable_strict(model.parameters) if model.parameters else None,
        )
        conn.execute(
            "INSERT INTO models_virtual_model_members (virtual_model_name, universal_id, position, parameters) VALUES (?, ?, ?, ?)",
            params_member,
        )


def sync_delete_virtual_model(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("DELETE FROM models_virtual_models WHERE name = ?", (name,)).rowcount > 0


async def get_virtual_model_query(
    database: aiosqlite.Connection,
    name: str,
) -> VirtualModelConfig | None:
    rows = await query_to_dicts(
        database,
        "SELECT * FROM models_virtual_models WHERE name = ?",
        (name,),
    )
    if not rows:
        return None
    members = await query_to_dicts(
        database,
        "SELECT * FROM models_virtual_model_members WHERE virtual_model_name = ? ORDER BY position",
        (name,),
    )
    return row_to_virtual_model(rows[0], members)


async def list_all_virtual_models_query(
    database: aiosqlite.Connection,
) -> list[VirtualModelConfig]:
    rows = await query_to_dicts(database, "SELECT * FROM models_virtual_models ORDER BY name")
    if not rows:
        return []
    all_members = await query_to_dicts(
        database,
        "SELECT * FROM models_virtual_model_members ORDER BY virtual_model_name, position",
    )
    members_by_virtual_model_name: dict[str, list[SQLiteRowDict]] = {}
    for member in all_members:
        virtual_model_name = member.get("virtual_model_name")
        if isinstance(virtual_model_name, str):
            members = members_by_virtual_model_name.get(virtual_model_name)
            if members is None:
                members = []
                members_by_virtual_model_name[virtual_model_name] = members
            members.append(member)
    return [
        row_to_virtual_model(
            row,
            members_by_virtual_model_name.get(str(row.get("name")), []),
        )
        for row in rows
    ]


async def find_virtual_models_using_universal_ids_query(
    database: aiosqlite.Connection,
    universal_ids: list[str],
) -> dict[str, list[str]]:
    if not universal_ids:
        return {}
    result: dict[str, list[str]] = {uid: [] for uid in universal_ids}
    for start_index in range(0, len(universal_ids), SQLITE_BATCH_SIZE):
        batch = universal_ids[start_index : start_index + SQLITE_BATCH_SIZE]
        placeholders = ",".join("?" * len(batch))
        rows = await query_to_dicts(
            database,
            f"SELECT universal_id, virtual_model_name FROM models_virtual_model_members WHERE universal_id IN ({placeholders})",
            tuple(batch),
        )
        for row in rows:
            universal_id = row.get("universal_id")
            virtual_model_name = row.get("virtual_model_name")
            if isinstance(universal_id, str) and isinstance(virtual_model_name, str):
                result[universal_id].append(virtual_model_name)
    return result
