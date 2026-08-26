"""SoAI - Database models catalog upsert operations [backend/database/repositories/models/catalog_upsert.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.timing.epoch import epoch_ms
from core.validation.boolean_coercion import coerce_bool_with_default
from database.core.json_codec import safe_json_serialize
from database.core.query_execution import sync_fetch_all_as_dicts

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("sync_upsert_models",)

KNOWN_MODEL_COLS: frozenset[str] = frozenset(
    (
        "universal_id",
        "plugin_name",
        "model_id",
        "source_model_id",
        "display_name",
        "description",
        "content_hash",
        "file_path",
        "size_bytes",
        "file_modified_at_ms",
        "created_at_ms",
        "last_discovered_at_ms",
        "last_modified_at_ms",
        "last_used_at_ms",
        "last_used_revision",
        "request_count",
        "context_window_tokens",
        "raw_details",
        "parameter_version",
        "provider_id",
        "status",
        "is_enabled",
        "capabilities",
        "openai_capabilities_overrides",
        "tags",
        "family",
        "license",
        "quantization",
    ),
)

USAGE_PRESERVED_ON_CONFLICT_COLS: frozenset[str] = frozenset(
    ("last_used_at_ms", "last_used_revision", "request_count")
)
LOGGER_NAME = "SoAI.database.repositories.catalog_upsert"


def sync_upsert_models(
    conn: sqlite3.Connection,
    models_to_upsert: list[JSONDict],
) -> None:
    if not models_to_upsert:
        return
    now = epoch_ms()
    allowed_columns = KNOWN_MODEL_COLS
    plugin_rows = sync_fetch_all_as_dicts(conn.execute("SELECT plugin_name FROM plugins_catalog"))
    valid_plugins = {
        plugin_name_value
        for row in plugin_rows
        if isinstance((plugin_name_value := row.get("plugin_name")), str)
    }
    valid_providers: set[str | None] = {
        provider_id_value
        for row in sync_fetch_all_as_dicts(conn.execute("SELECT id FROM models_external_providers"))
        if isinstance((provider_id_value := row.get("id")), str)
    }
    valid_providers.add(None)
    records: list[JSONDict] = []
    for model_entry in models_to_upsert:
        normalized_entry = dict(model_entry)
        plugin_name = normalized_entry.get("plugin_name")
        provider_id = normalized_entry.get("provider_id")
        if not isinstance(plugin_name, str) or plugin_name not in valid_plugins:
            raise ValidationError(
                "Cannot upsert model: plugin not found in plugins_catalog.",
                details={
                    "universal_id": normalized_entry.get("universal_id"),
                    "plugin_name": plugin_name,
                },
            )
        if provider_id is not None and not isinstance(provider_id, str):
            raise ValidationError(
                "Cannot upsert model: provider_id not found in models_external_providers.",
                details={
                    "universal_id": normalized_entry.get("universal_id"),
                    "provider_id": provider_id,
                },
            )
        if provider_id not in valid_providers:
            get_logger(LOGGER_NAME).warning(
                "Skipping discovered provider-backed model because provider '%s' no longer exists.",
                provider_id,
            )
            continue
        raw_details = {
            key: value
            for key, value in normalized_entry.items()
            if key not in allowed_columns and key not in {"size"}
        }
        record: JSONDict = {
            key: value for key, value in normalized_entry.items() if key in allowed_columns
        }
        if "last_discovered_at_ms" in allowed_columns:
            record["last_discovered_at_ms"] = record.get("last_discovered_at_ms", now)
        if "parameter_version" in allowed_columns:
            record["parameter_version"] = record.get("parameter_version", 0)
        if "status" in allowed_columns:
            record["status"] = "active"
        if "created_at_ms" in allowed_columns:
            record["created_at_ms"] = record.get("created_at_ms", now)
        if "last_modified_at_ms" in allowed_columns:
            record["last_modified_at_ms"] = record.get("last_modified_at_ms", now)
        if "is_enabled" in allowed_columns:
            raw_enabled = record.get("is_enabled")
            enabled = coerce_bool_with_default(raw_enabled, default=True, strict=True)
            record["is_enabled"] = 1 if enabled else 0
        if "request_count" in allowed_columns:
            record["request_count"] = record.get("request_count", 0)
        model_identifier = str(normalized_entry.get("universal_id", "unknown"))
        if "capabilities" in allowed_columns:
            record["capabilities"] = safe_json_serialize(
                record.get("capabilities"),
                "capabilities",
                model_identifier,
            )
        if "tags" in allowed_columns:
            record["tags"] = safe_json_serialize(record.get("tags"), "tags", model_identifier)
        if "openai_capabilities_overrides" in allowed_columns:
            record["openai_capabilities_overrides"] = safe_json_serialize(
                record.get("openai_capabilities_overrides"),
                "openai_capabilities_overrides",
                model_identifier,
            )
        if "raw_details" in allowed_columns:
            record["raw_details"] = safe_json_serialize(
                raw_details,
                "raw_details",
                model_identifier,
            )
        records.append(record)
    if not records:
        return
    all_columns: set[str] = set()
    for record_entry in records:
        all_columns.update(record_entry.keys())
    cols = sorted(list(all_columns))
    update_cols = [
        column
        for column in cols
        if column
        not in {"universal_id", "created_at_ms", "is_enabled"} | USAGE_PRESERVED_ON_CONFLICT_COLS
    ]
    sql = f"INSERT INTO models_catalog ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)}) ON CONFLICT(universal_id) DO UPDATE SET {', '.join(f'{column}=excluded.{column}' for column in update_cols)}"
    conn.executemany(
        sql,
        [[record_entry.get(column) for column in cols] for record_entry in records],
    )
