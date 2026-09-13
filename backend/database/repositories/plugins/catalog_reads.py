"""SoAI - Database plugin catalog read queries [backend/database/repositories/plugins/catalog_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.state.state_names import PLUGIN_STATE_ABSENT, PLUGIN_STATE_DELETING
from core.types.json_value import coerce_json_dict, filter_json_mapping_strict
from database.core.query_execution import query_to_dicts

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_all_listable_plugins_query",
    "get_all_plugins_query",
    "get_authoritative_plugin_states_query",
    "get_latest_plugin_usage_query",
    "get_plugin_by_name_query",
)


def _remove_internal_usage_revision(row: JSONDict) -> JSONDict:
    row.pop("last_used_revision", None)
    return row


async def get_all_listable_plugins_query(
    database: aiosqlite.Connection,
    plugin_name: str | None = None,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        """SELECT * FROM plugins_catalog AS plugin
        WHERE plugin.state NOT IN (?, ?, 'ACTIVATING')
            AND NOT EXISTS (
                SELECT 1 FROM plugin_clone_target_reservations AS reservation
                WHERE reservation.target_plugin_name = plugin.plugin_name
            ) AND (? IS NULL OR plugin.plugin_name = ?)""",
        (PLUGIN_STATE_ABSENT, PLUGIN_STATE_DELETING, plugin_name, plugin_name),
    )
    result: list[JSONDict] = []
    for row in rows:
        parsed = coerce_json_dict(row)
        if parsed is not None:
            result.append(_remove_internal_usage_revision(parsed))
    return result


async def get_all_plugins_query(
    database: aiosqlite.Connection,
) -> list[JSONDict]:
    rows = await query_to_dicts(database, "SELECT * FROM plugins_catalog")
    result: list[JSONDict] = []
    for row in rows:
        parsed = coerce_json_dict(row)
        if parsed is not None:
            result.append(_remove_internal_usage_revision(parsed))
    return result


async def get_plugin_by_name_query(
    database: aiosqlite.Connection,
    plugin_name: str,
) -> JSONDict | None:
    rows = await query_to_dicts(
        database,
        "SELECT * FROM plugins_catalog WHERE plugin_name = ?",
        (plugin_name,),
    )
    if not rows:
        return None
    parsed = coerce_json_dict(rows[0])
    return _remove_internal_usage_revision(parsed) if parsed is not None else None


async def get_latest_plugin_usage_query(
    database: aiosqlite.Connection,
) -> JSONDict | None:
    rows = await query_to_dicts(
        database,
        "SELECT plugin_name, last_used_at_ms, last_used_revision AS revision FROM plugins_catalog WHERE last_used_revision > 0 ORDER BY last_used_revision DESC LIMIT 1",
    )
    return coerce_json_dict(rows[0]) if rows else None


async def get_authoritative_plugin_states_query(
    database: aiosqlite.Connection,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        """SELECT plugin.plugin_name, plugin.state,
            COALESCE(publication.publication_sequence, 0) AS publication_sequence
        FROM plugins_catalog AS plugin
        LEFT JOIN (
            SELECT plugin_name, MAX(id) AS publication_sequence
            FROM plugin_authoritative_state_outbox GROUP BY plugin_name
        ) AS publication ON publication.plugin_name = plugin.plugin_name
        WHERE plugin.state NOT IN (?, ?, 'ACTIVATING')
            AND NOT EXISTS (
                SELECT 1 FROM plugin_clone_target_reservations AS reservation
                WHERE reservation.target_plugin_name = plugin.plugin_name
            )""",
        (PLUGIN_STATE_ABSENT, PLUGIN_STATE_DELETING),
    )
    return [
        filter_json_mapping_strict(
            row, error_message="The authoritative plugin state snapshot is invalid."
        )
        for row in rows
    ]
