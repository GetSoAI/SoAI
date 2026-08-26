"""SoAI - Plugin repository statistics aggregation [backend/database/repositories/plugins/stats.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.core.sqlite_numbers import coerce_non_negative_int_from_sqlite
from database.repositories.plugins.catalog_stats_queries import (
    get_stats_for_plugins_query,
)

if TYPE_CHECKING:
    from core.database.protocols import DatabaseReaderProtocol

__all__ = ("compute_plugin_stats",)


async def compute_plugin_stats(
    reader: DatabaseReaderProtocol,
    plugin_names: list[str],
) -> dict[str, dict[str, int]]:
    normalized: list[str] = []
    for raw_name in plugin_names:
        if not isinstance(raw_name, str):
            continue
        candidate = raw_name.strip()
        if candidate:
            normalized.append(candidate)
    if not normalized:
        return {}
    stats = {name: {"model_count": 0, "provider_count": 0} for name in normalized}
    chunk_size = 400
    for offset in range(0, len(normalized), chunk_size):
        chunk = normalized[offset : offset + chunk_size]
        rows = await reader.execute_read(get_stats_for_plugins_query, chunk)
        for row in rows:
            name = row.get("plugin_name")
            if not isinstance(name, str) or name not in stats:
                continue
            stats[name]["model_count"] += coerce_non_negative_int_from_sqlite(
                row.get("model_count"),
            )
            stats[name]["provider_count"] += coerce_non_negative_int_from_sqlite(
                row.get("provider_count"),
            )
    return stats
