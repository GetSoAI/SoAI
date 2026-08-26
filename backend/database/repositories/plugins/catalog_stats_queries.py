"""SoAI - Database plugin catalog stats queries [backend/database/repositories/plugins/catalog_stats_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.types.json_value import coerce_json_dict
from database.core.query_execution import query_to_dicts

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_stats_for_plugins_query",)


async def get_stats_for_plugins_query(
    database: aiosqlite.Connection,
    plugin_names: list[str],
) -> list[JSONDict]:
    if not plugin_names:
        return []
    placeholders = ", ".join(["?"] * len(plugin_names))
    query = f"""
        SELECT plugin_name AS plugin_name, COUNT(*) AS model_count, 0 AS provider_count
        FROM models_catalog
        WHERE plugin_name IN ({placeholders})
        GROUP BY plugin_name
        UNION ALL
        SELECT plugin_name AS plugin_name, 0 AS model_count, COUNT(*) AS provider_count
        FROM models_external_providers
        WHERE plugin_name IN ({placeholders})
        GROUP BY plugin_name
    """
    args = tuple(plugin_names + plugin_names)
    rows = await query_to_dicts(database, query, args)
    return [coerce_json_dict(row) or {} for row in rows]
