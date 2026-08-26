"""SoAI - Provider mutation uniqueness conflicts [backend/database/repositories/plugins/provider_mutation_conflicts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from database.core.sqlite_values import SQLiteValue

__all__ = ("read_provider_conflict_revision", "read_provider_revision")


def read_provider_revision(
    connection: sqlite3.Connection,
    *,
    plugin_name: str,
    provider_id: str,
) -> int | None:
    row = connection.execute(
        "SELECT revision FROM models_external_providers WHERE id = ? AND plugin_name = ?",
        (provider_id, plugin_name),
    ).fetchone()
    return row["revision"] if row is not None else None


def read_provider_conflict_revision(
    connection: sqlite3.Connection,
    *,
    plugin_name: str,
    provider_id: str,
    normalized_fields: dict[str, SQLiteValue],
    include_same_id: bool,
) -> int | None:
    predicates = ["api_url = ?"]
    values: list[SQLiteValue] = [normalized_fields["api_url"]]
    canonical_name = normalized_fields.get("canonical_name")
    if canonical_name is not None:
        predicates.append("canonical_name = ?")
        values.append(canonical_name)
    scoped_conflict = f"(plugin_name = ? AND ({' OR '.join(predicates)}))"
    if include_same_id:
        query = f"SELECT revision FROM models_external_providers WHERE id = ? OR {scoped_conflict}"
        parameters = [provider_id, plugin_name, *values]
    else:
        query = (
            f"SELECT revision FROM models_external_providers WHERE id != ? AND {scoped_conflict}"
        )
        parameters = [provider_id, plugin_name, *values]
    row = connection.execute(query, parameters).fetchone()
    return row["revision"] if row is not None else None
