"""SoAI - Database plugins state operations [backend/database/repositories/plugins/state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

import aiosqlite

from core.serialization.json import serialize_json_compact_stable_strict
from core.state.compatibility import CompatibilityInfo
from core.state.state_names import PLUGIN_STATE_INCOMPATIBLE
from core.timing.epoch import epoch_ms
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.query_execution import query_one_to_dict

__all__ = (
    "get_incompatible_state",
    "get_plugin_state_only_query",
    "sync_clear_incompatibility",
    "sync_mark_plugin_user_enabled_once",
    "sync_mark_welcome_message_logged",
    "sync_set_incompatibility",
    "sync_set_incompatibility_override",
    "sync_update_plugin_runtime_loaded",
    "sync_update_plugin_state",
    "sync_update_plugin_state_batch",
)


async def get_plugin_state_only_query(
    database: aiosqlite.Connection,
    plugin_name: str,
) -> str | None:
    row = await query_one_to_dict(
        database,
        "SELECT state FROM plugins_catalog WHERE plugin_name = ?",
        (plugin_name,),
    )
    if row is None:
        return None
    state = row.get("state")
    return state if isinstance(state, str) else None


def sync_update_plugin_state(conn: sqlite3.Connection, plugin_name: str, state: str) -> None:
    conn.execute(
        "UPDATE plugins_catalog SET state = ?, last_seen_at_ms = ? WHERE plugin_name = ?",
        (state, epoch_ms(), plugin_name),
    )


def sync_update_plugin_state_batch(
    conn: sqlite3.Connection,
    plugin_names: list[str],
    state: str,
) -> None:
    for batch_start in range(0, len(plugin_names), SQLITE_BATCH_SIZE):
        batch = plugin_names[batch_start : batch_start + SQLITE_BATCH_SIZE]
        placeholders = ",".join("?" for _ in batch)
        params = [state, epoch_ms(), *batch]
        conn.execute(
            f"UPDATE plugins_catalog SET state = ?, last_seen_at_ms = ? WHERE plugin_name IN ({placeholders})",
            params,
        )


def sync_update_plugin_runtime_loaded(
    conn: sqlite3.Connection,
    plugin_name: str,
    runtime_loaded: bool,
) -> None:
    conn.execute(
        "UPDATE plugins_catalog SET runtime_loaded = ?, last_seen_at_ms = ? WHERE plugin_name = ?",
        (int(runtime_loaded), epoch_ms(), plugin_name),
    )


def sync_set_incompatibility(
    conn: sqlite3.Connection,
    plugin_name: str,
    info: CompatibilityInfo,
    state: str,
) -> None:
    conn.execute(
        "UPDATE plugins_catalog SET state = ?, incompatibility_reason = ?, incompatibility_override = ?, incompatibility_details = ?, incompatibility_message = ?, last_seen_at_ms = ? WHERE plugin_name = ?",
        (
            state,
            info.reason.value if info.reason else None,
            int(bool(info.is_overridden)),
            (
                serialize_json_compact_stable_strict(info.details)
                if info.details is not None
                else None
            ),
            info.message,
            epoch_ms(),
            plugin_name,
        ),
    )


def sync_clear_incompatibility(conn: sqlite3.Connection, plugin_name: str) -> None:
    conn.execute(
        "UPDATE plugins_catalog SET incompatibility_reason = NULL, incompatibility_override = 0, incompatibility_details = NULL, incompatibility_message = NULL, last_seen_at_ms = ? WHERE plugin_name = ?",
        (epoch_ms(), plugin_name),
    )


def sync_set_incompatibility_override(
    conn: sqlite3.Connection,
    plugin_name: str,
    override: bool,
) -> None:
    conn.execute(
        "UPDATE plugins_catalog SET incompatibility_override = ?, last_seen_at_ms = ? WHERE plugin_name = ?",
        (int(bool(override)), epoch_ms(), plugin_name),
    )


def sync_mark_welcome_message_logged(conn: sqlite3.Connection, plugin_name: str) -> None:
    conn.execute(
        "UPDATE plugins_catalog SET welcome_message_logged = 1 WHERE plugin_name = ?",
        (plugin_name,),
    )


def sync_mark_plugin_user_enabled_once(conn: sqlite3.Connection, plugin_name: str) -> None:
    conn.execute(
        "UPDATE plugins_catalog SET user_enabled_once = 1 WHERE plugin_name = ?",
        (plugin_name,),
    )


def get_incompatible_state() -> str:
    return PLUGIN_STATE_INCOMPATIBLE
