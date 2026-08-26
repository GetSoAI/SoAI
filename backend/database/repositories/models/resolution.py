"""SoAI - Database models resolution operations [backend/database/repositories/models/resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import aiosqlite

from database.core.query_execution import query_one_to_dict, query_to_dicts

__all__ = (
    "resolve_by_plugin_and_source_model_id_query",
    "resolve_by_provider_and_source_model_id_query",
)


async def resolve_by_plugin_and_source_model_id_query(
    database: aiosqlite.Connection,
    plugin_name: str,
    source_model_id: str,
) -> str | None:
    sql = "SELECT universal_id FROM models_catalog WHERE plugin_name = ? AND source_model_id = ? AND status = 'active' ORDER BY universal_id LIMIT 1"
    row = await query_one_to_dict(database, sql, (plugin_name, source_model_id))
    if row is None:
        return None
    universal_id = row.get("universal_id")
    return universal_id if isinstance(universal_id, str) else None


async def resolve_by_provider_and_source_model_id_query(
    database: aiosqlite.Connection,
    provider_canonical_name: str,
    source_model_id: str,
) -> str | None:
    rows = await query_to_dicts(
        database,
        """SELECT model.universal_id
        FROM models_catalog AS model
        JOIN models_external_providers AS provider ON provider.id = model.provider_id
        WHERE provider.canonical_name = ? AND model.source_model_id = ? AND model.status = 'active'
        ORDER BY model.universal_id LIMIT 2""",
        (provider_canonical_name, source_model_id),
    )
    if len(rows) != 1:
        return None
    universal_id = rows[0].get("universal_id")
    return universal_id if isinstance(universal_id, str) else None
