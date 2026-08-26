"""SoAI - Database plugin runtime process tracking queries [backend/database/repositories/plugins/runtime_processes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import StateError, ValidationError
from core.runtime.backend_process_tracking import BackendProcessIdentity
from core.serialization.json import (
    normalize_for_json,
    serialize_json_compact_stable_strict,
)
from core.serialization.json_parsing import parse_json_value
from core.timing.epoch import epoch_ms
from database.core.query_execution import query_one_to_dict, query_to_dicts

if TYPE_CHECKING:
    from core.plugins.protocols_database import PluginRuntimeProcessesPayload

__all__ = (
    "get_runtime_processes_query",
    "list_plugins_with_runtime_processes_query",
    "sync_clear_runtime_processes",
    "sync_set_runtime_processes",
)


def _parse_runtime_processes(
    value: float | str | bytes | None,
    *,
    plugin_name: str,
) -> list[BackendProcessIdentity]:
    if value is None:
        return []
    if not isinstance(value, str):
        raise StateError(
            "Invalid runtime_processes value type in plugins_catalog.",
            operation="database.plugins.runtime_processes.parse",
            details={"plugin_name": plugin_name, "type": type(value).__name__},
        )
    try:
        parsed = parse_json_value(value)
    except ValidationError as exception:
        raise StateError(
            "Invalid runtime_processes JSON in plugins_catalog.",
            operation="database.plugins.runtime_processes.parse",
            details={"plugin_name": plugin_name},
            cause=exception,
        ) from exception
    if parsed is None:
        return []
    if not isinstance(parsed, list):
        raise StateError(
            "Invalid runtime_processes JSON shape in plugins_catalog.",
            operation="database.plugins.runtime_processes.parse",
            details={"plugin_name": plugin_name, "shape": type(parsed).__name__},
        )
    identities: list[BackendProcessIdentity] = []
    for item in parsed:
        if not isinstance(item, dict):
            raise StateError(
                "Invalid runtime_processes entry in plugins_catalog.",
                operation="database.plugins.runtime_processes.parse",
                details={"plugin_name": plugin_name},
            )
        pid = item.get("pid")
        create_time_ms = item.get("createTimeMs")
        if isinstance(pid, bool) or (not isinstance(pid, int)) or pid <= 0:
            raise StateError(
                "Invalid runtime_processes identity entry in plugins_catalog.",
                operation="database.plugins.runtime_processes.parse",
                details={"plugin_name": plugin_name, "identity": item},
            )
        if (
            isinstance(create_time_ms, bool)
            or (not isinstance(create_time_ms, int))
            or create_time_ms <= 0
        ):
            raise StateError(
                "Invalid runtime_processes identity entry in plugins_catalog.",
                operation="database.plugins.runtime_processes.parse",
                details={"plugin_name": plugin_name, "identity": item},
            )
        identities.append({"pid": pid, "createTimeMs": create_time_ms})
    return identities


async def get_runtime_processes_query(
    database: aiosqlite.Connection,
    plugin_name: str,
) -> list[BackendProcessIdentity]:
    row = await query_one_to_dict(
        database,
        "SELECT runtime_processes FROM plugins_catalog WHERE plugin_name = ?",
        (plugin_name,),
    )
    if row is None:
        return []
    return _parse_runtime_processes(row.get("runtime_processes"), plugin_name=plugin_name)


def sync_set_runtime_processes(
    conn: sqlite3.Connection,
    plugin_name: str,
    identities: list[BackendProcessIdentity],
) -> None:
    if not identities:
        sync_clear_runtime_processes(conn, plugin_name)
        return
    payload = serialize_json_compact_stable_strict(normalize_for_json(identities))
    cursor = conn.execute(
        "UPDATE plugins_catalog SET runtime_processes = ?, runtime_processes_updated_at_ms = ? WHERE plugin_name = ?",
        (payload, epoch_ms(), plugin_name),
    )
    if cursor.rowcount == 0:
        raise StateError(
            "Failed to set runtime_processes: plugin record not found.",
            operation="database.plugins.runtime_processes.set",
            details={"plugin_name": plugin_name},
        )


def sync_clear_runtime_processes(conn: sqlite3.Connection, plugin_name: str) -> None:
    cursor = conn.execute(
        "UPDATE plugins_catalog SET runtime_processes = NULL, runtime_processes_updated_at_ms = ? WHERE plugin_name = ?",
        (epoch_ms(), plugin_name),
    )
    if cursor.rowcount == 0:
        raise StateError(
            "Failed to clear runtime_processes: plugin record not found.",
            operation="database.plugins.runtime_processes.clear",
            details={"plugin_name": plugin_name},
        )


async def list_plugins_with_runtime_processes_query(
    database: aiosqlite.Connection,
) -> list[PluginRuntimeProcessesPayload]:
    rows = await query_to_dicts(
        database,
        """
        SELECT plugin_name, state, supports_backend_process_tracking, runtime_processes
        FROM plugins_catalog
        WHERE runtime_processes IS NOT NULL
          AND supports_backend_process_tracking = 1
          AND json_array_length(runtime_processes) > 0
        """,
    )
    result: list[PluginRuntimeProcessesPayload] = []
    for row in rows:
        plugin_name = row.get("plugin_name")
        state = row.get("state")
        supports_tracking = row.get("supports_backend_process_tracking")
        runtime_processes_value = row.get("runtime_processes")
        if not isinstance(plugin_name, str) or not plugin_name.strip():
            raise StateError(
                "Invalid plugin_name value in plugins_catalog runtime process listing.",
                operation="database.plugins.runtime_processes.list",
                details={"plugin_name": repr(plugin_name)},
            )
        if not isinstance(state, str):
            raise StateError(
                "Invalid state value in plugins_catalog runtime process listing.",
                operation="database.plugins.runtime_processes.list",
                details={"plugin_name": plugin_name, "state": repr(state)},
            )
        if isinstance(supports_tracking, bool) or (not isinstance(supports_tracking, int)):
            raise StateError(
                "Invalid supports_backend_process_tracking value in plugins_catalog runtime process listing.",
                operation="database.plugins.runtime_processes.list",
                details={
                    "plugin_name": plugin_name,
                    "supports_backend_process_tracking": repr(supports_tracking),
                },
            )
        runtime_processes = _parse_runtime_processes(
            runtime_processes_value,
            plugin_name=plugin_name,
        )
        payload: PluginRuntimeProcessesPayload = {
            "plugin_name": plugin_name,
            "state": state,
            "supports_backend_process_tracking": supports_tracking,
            "runtime_processes": runtime_processes,
        }
        result.append(payload)
    return result
