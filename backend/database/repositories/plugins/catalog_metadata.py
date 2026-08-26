"""SoAI - Plugin catalog metadata persistence [backend/database/repositories/plugins/catalog_metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.errors.exceptions import ValidationError
from core.serialization.json import serialize_json_compact_stable_strict
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, JSONValue
from core.validation.record_fields import require_json_list, require_json_object

__all__ = ("sync_update_plugin_catalog_metadata",)


def sync_update_plugin_catalog_metadata(
    conn: sqlite3.Connection,
    plugin_name: str,
    parameter_schema: JSONDict | None,
    backend_variant_options: list[JSONDict] | None,
) -> None:
    updates: list[str] = []
    values: list[str | int] = []
    if parameter_schema is not None:
        schema = require_json_object(
            parameter_schema,
            label="parameter_schema",
            build_error=ValidationError,
        )
        updates.append("parameter_schema = ?")
        values.append(serialize_json_compact_stable_strict(schema))
    if backend_variant_options is not None:
        options: list[JSONValue] = list(backend_variant_options)
        normalized_options = require_json_list(
            options,
            label="backend_variant_options",
            build_error=ValidationError,
        )
        updates.append("backend_variant_options = ?")
        values.append(serialize_json_compact_stable_strict(normalized_options))
    if not updates:
        return
    updates.append("last_seen_at_ms = ?")
    values.append(epoch_ms())
    values.append(plugin_name)
    conn.execute(
        f"UPDATE plugins_catalog SET {', '.join(updates)} WHERE plugin_name = ?",
        tuple(values),
    )
