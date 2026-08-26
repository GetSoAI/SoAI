"""SoAI - Database models catalog read operations [backend/database/repositories/models/catalog_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.models.source_identifier import require_source_model_id
from core.types.json_value import coerce_json_dict
from database.core.data_conversions import SQLITE_BATCH_SIZE
from database.core.json_codec import safe_json_deserialize
from database.core.query_execution import query_one_to_dict, query_to_dicts
from database.repositories.row_formatting import format_row

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "format_model_info",
    "get_all_models_by_plugin_query",
    "get_model_info_query",
    "get_models_info_query",
    "list_model_rows_query",
    "get_latest_model_usage_query",
)


def format_model_info(row: SQLiteRowDict | None) -> JSONDict | None:
    model_info = format_row(row)
    if model_info is None or row is None:
        return model_info
    plugin_name_value = model_info.get("plugin_name")
    if isinstance(plugin_name_value, str) and plugin_name_value.strip():
        model_info["plugin"] = plugin_name_value.strip()
    model_info.pop("plugin_name", None)
    model_info.pop("last_used_revision", None)
    file_path_value = model_info.get("file_path")
    if isinstance(file_path_value, str) and file_path_value.strip():
        model_info["path"] = file_path_value
    model_info.pop("file_path", None)
    raw_details = safe_json_deserialize(row.get("raw_details"), None)
    if raw_details is not None and not isinstance(raw_details, dict):
        raise ValidationError(
            "models_catalog.raw_details must be a JSON object or null.",
            details={"universal_id": model_info.get("universal_id")},
        )
    if isinstance(raw_details, dict):
        protected_keys = set(model_info.keys())
        for key, value in raw_details.items():
            if isinstance(key, str):
                if key == "size":
                    continue
                if key in protected_keys:
                    continue
                model_info[key] = value
    model_info.pop("raw_details", None)
    capabilities_value = safe_json_deserialize(row.get("capabilities"), [])
    if not isinstance(capabilities_value, list):
        raise ValidationError(
            "models_catalog.capabilities must be a JSON list or null.",
            details={"universal_id": model_info.get("universal_id")},
        )
    model_info["capabilities"] = capabilities_value
    tags_value = safe_json_deserialize(row.get("tags"), [])
    if not isinstance(tags_value, list):
        raise ValidationError(
            "models_catalog.tags must be a JSON list or null.",
            details={"universal_id": model_info.get("universal_id")},
        )
    model_info["tags"] = tags_value
    overrides_value = safe_json_deserialize(row.get("openai_capabilities_overrides"), None)
    if overrides_value is None:
        model_info["openai_capabilities_overrides"] = None
    elif isinstance(overrides_value, dict):
        model_info["openai_capabilities_overrides"] = overrides_value or None
    else:
        raise ValidationError(
            "models_catalog.openai_capabilities_overrides must be a JSON object or null.",
            details={"universal_id": model_info.get("universal_id")},
        )
    model_info["source_model_id"] = require_source_model_id(model_info)
    return model_info


async def get_all_models_by_plugin_query(
    database: aiosqlite.Connection,
) -> dict[str, dict[str, JSONDict]]:
    result: dict[str, dict[str, JSONDict]] = defaultdict(dict)
    for row in await query_to_dicts(database, "SELECT * FROM models_catalog"):
        plugin_name = row.get("plugin_name")
        model_id = row.get("model_id")
        if isinstance(plugin_name, str) and isinstance(model_id, str):
            formatted = format_model_info(row)
            if formatted is not None:
                result[plugin_name][model_id] = formatted
    return dict(result)


async def get_model_info_query(
    database: aiosqlite.Connection,
    universal_id: str,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        "SELECT * FROM models_catalog WHERE universal_id = ?",
        (universal_id,),
    )
    return format_model_info(row)


async def get_models_info_query(
    database: aiosqlite.Connection,
    universal_ids: list[str],
) -> dict[str, JSONDict]:
    if not universal_ids:
        return {}
    all_rows: list[SQLiteRowDict] = []
    for start in range(0, len(universal_ids), SQLITE_BATCH_SIZE):
        batch = universal_ids[start : start + SQLITE_BATCH_SIZE]
        placeholders = ",".join("?" for _ in batch)
        rows = await query_to_dicts(
            database,
            f"SELECT * FROM models_catalog WHERE universal_id IN ({placeholders})",
            tuple(batch),
        )
        all_rows.extend(rows)
    formatted_rows: dict[str, JSONDict] = {}
    for row in all_rows:
        universal_id_value = row.get("universal_id")
        if not isinstance(universal_id_value, str):
            continue
        formatted = format_model_info(row)
        if formatted:
            formatted_rows[universal_id_value] = formatted
    return formatted_rows


async def list_model_rows_query(
    database: aiosqlite.Connection,
) -> list[JSONDict]:
    rows = await query_to_dicts(
        database,
        """SELECT model.*, plugin.state AS plugin_catalog_state
        FROM models_catalog AS model
        LEFT JOIN plugins_catalog AS plugin ON plugin.plugin_name = model.plugin_name
        ORDER BY model.display_name""",
    )
    return [formatted for row in rows if (formatted := format_model_info(row))]


async def get_latest_model_usage_query(
    database: aiosqlite.Connection,
) -> JSONDict | None:
    row = await query_one_to_dict(
        database,
        "SELECT universal_id, last_used_at_ms, last_used_revision AS revision FROM models_catalog WHERE last_used_revision > 0 ORDER BY last_used_revision DESC LIMIT 1",
    )
    return coerce_json_dict(row)
