"""SoAI - Database plugin catalog write operations [backend/database/repositories/plugins/catalog_writes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.serialization.json import serialize_json_compact_stable_strict
from core.state.compatibility import CompatibilityInfo
from core.state.state_names import PLUGIN_STATE_NOT_DETECTED
from core.timing.epoch import epoch_ms
from core.validation.record_fields import (
    require_bool,
    require_json_list,
    require_json_object,
)
from database.core.row_booleans import coerce_sqlite_bool_int

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from database.core.sqlite_values import SQLiteValue

__all__ = (
    "sync_add_or_update_plugin",
    "sync_create_uploading_placeholder",
    "sync_permanently_delete_plugin_record",
)

LOGGER_NAME = "SoAI.database.repositories.catalog_writes"


def _coerce_sqlite_value(value: JSONValue) -> SQLiteValue:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float | str | bytes):
        return value
    return None


def sync_create_uploading_placeholder(conn: sqlite3.Connection, plugin_name: str) -> bool:
    logger = get_logger(LOGGER_NAME)
    now = epoch_ms()
    try:
        conn.execute(
            "INSERT INTO plugins_catalog (plugin_name, first_seen_at_ms, last_seen_at_ms, state, supports_backend_installation, supports_model_deletion, supports_model_download, has_configuration, supports_external_providers, external_provider_mode, persistent, local_resources, local_models, user_enabled_once) VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, 'none', 0, 0, 0, 0)",
            (plugin_name, now, now, PLUGIN_STATE_NOT_DETECTED),
        )
        return True
    except sqlite3.IntegrityError:
        logger.warning(
            "Attempted to create uploading placeholder for existing plugin '%s'.",
            plugin_name,
        )
        return False


def sync_add_or_update_plugin(
    conn: sqlite3.Connection,
    plugin_data: JSONDict,
    state: str | None,
    incompatibility: CompatibilityInfo | None,
    override: bool | None,
) -> None:
    plugin_name = plugin_data.get("plugin_name")
    if not plugin_name:
        raise ValidationError("plugin_data must contain a 'plugin_name'")
    base_columns = _catalog_base_columns()
    bool_columns = _catalog_bool_columns()
    params: list[SQLiteValue] = []
    for column in base_columns:
        params.append(_column_value(plugin_data, column, bool_columns))
    state_value = state if isinstance(state, str) else plugin_data.get("state")
    explicit_state_provided = isinstance(state_value, str) and bool(state_value)
    resolved_state = state_value or PLUGIN_STATE_NOT_DETECTED
    if not isinstance(resolved_state, str):
        resolved_state = PLUGIN_STATE_NOT_DETECTED
    resolved_override = override
    if resolved_override is None:
        resolved_override = incompatibility.is_overridden if incompatibility else False
    reason_value = (
        incompatibility.reason.value if incompatibility and incompatibility.reason else None
    )
    details_value = (
        serialize_json_compact_stable_strict(incompatibility.details)
        if incompatibility and incompatibility.details is not None
        else None
    )
    message_value = incompatibility.message if incompatibility else None
    now = epoch_ms()
    final_columns = base_columns + [
        "first_seen_at_ms",
        "last_seen_at_ms",
        "state",
        "incompatibility_reason",
        "incompatibility_override",
        "incompatibility_details",
        "incompatibility_message",
    ]
    params.extend(
        [
            now,
            now,
            resolved_state,
            reason_value,
            coerce_sqlite_bool_int(resolved_override, default=False),
            details_value,
            message_value,
        ],
    )
    update_columns = [col for col in base_columns if col != "plugin_name"] + ["last_seen_at_ms"]
    if explicit_state_provided:
        update_columns.append("state")
    update_columns.extend(
        [
            "incompatibility_reason",
            "incompatibility_override",
            "incompatibility_details",
            "incompatibility_message",
        ],
    )
    insert_cols = ", ".join(final_columns)
    placeholders = ", ".join(["?"] * len(params))
    update_clause = ", ".join(f"{col}=excluded.{col}" for col in update_columns)
    conn.execute(
        f"INSERT INTO plugins_catalog ({insert_cols}) VALUES ({placeholders}) ON CONFLICT(plugin_name) DO UPDATE SET {update_clause};",
        tuple(params),
    )


def sync_permanently_delete_plugin_record(conn: sqlite3.Connection, plugin_name: str) -> int:
    cursor = conn.execute("DELETE FROM plugins_catalog WHERE plugin_name = ?", (plugin_name,))
    conn.execute(
        "DELETE FROM plugin_clone_transactions WHERE target_plugin_name = ? AND committed = 1",
        (plugin_name,),
    )
    return cursor.rowcount


def _require_key(plugin_data: JSONDict, key: str) -> JSONValue:
    if key not in plugin_data:
        raise ValidationError(f"plugin_data is missing required field '{key}'.")
    return plugin_data.get(key)


def _column_value(
    plugin_data: JSONDict,
    column: str,
    bool_columns: set[str],
) -> SQLiteValue:
    if column in {"aliases", "modalities", "model_types"}:
        return serialize_json_compact_stable_strict(_require_json_list(plugin_data, column))
    if column in _json_object_columns():
        return serialize_json_compact_stable_strict(_require_json_dict(plugin_data, column))
    if column == "backend_variant_options":
        return serialize_json_compact_stable_strict(_require_json_list(plugin_data, column))
    if column == "backend_status":
        status_value = _require_key(plugin_data, column)
        if status_value is None:
            return None
        return serialize_json_compact_stable_strict(_require_json_dict(plugin_data, column))
    if column in bool_columns:
        return int(_require_bool(plugin_data, column))
    return _coerce_sqlite_value(_require_key(plugin_data, column))


def _require_bool(plugin_data: JSONDict, key: str) -> bool:
    return require_bool(
        _require_key(plugin_data, key),
        label=key,
        build_error=ValidationError,
        invalid_message=f"plugin_data field '{key}' must be a boolean.",
    )


def _require_json_list(plugin_data: JSONDict, key: str) -> list[JSONValue]:
    return require_json_list(
        _require_key(plugin_data, key),
        label=key,
        build_error=ValidationError,
        invalid_message=f"plugin_data field '{key}' must be a JSON array.",
    )


def _require_json_dict(plugin_data: JSONDict, key: str) -> JSONDict:
    return require_json_object(
        _require_key(plugin_data, key),
        label=key,
        build_error=ValidationError,
        invalid_message=f"plugin_data field '{key}' must be a JSON object.",
    )


def _catalog_base_columns() -> list[str]:
    return [
        "plugin_name",
        "name",
        "description_soaiplugin",
        "website_soaiplugin",
        "author_soaiplugin",
        "version_soaiplugin",
        "license_soaiplugin",
        "license_managed_backend",
        "core_compat",
        "aliases",
        "dependencies",
        "modalities",
        "file_path",
        "file_hash",
        "supports_backend_installation",
        "supports_backend_process_tracking",
        "supports_model_deletion",
        "supports_model_download",
        "has_configuration",
        "supports_gpu_binding",
        "supports_external_providers",
        "external_provider_mode",
        "external_provider_defaults",
        "persistent",
        "local_resources",
        "local_models",
        "supports_cloning",
        "max_concurrent_requests",
        "model_repository",
        "model_types",
        "website_backend",
        "required_system_capabilities",
        "openai_capabilities",
        "default_configuration",
        "parameter_schema",
        "backend_variant_options",
        "supports_model_search",
        "supports_model_variant_discovery",
        "runtime_loaded",
        "backend_status",
        "catalog_reconciled_at_ms",
    ]


def _catalog_bool_columns() -> set[str]:
    return {
        "supports_backend_installation",
        "supports_backend_process_tracking",
        "supports_model_deletion",
        "supports_model_download",
        "has_configuration",
        "supports_gpu_binding",
        "supports_external_providers",
        "persistent",
        "local_resources",
        "local_models",
        "supports_cloning",
        "supports_model_search",
        "supports_model_variant_discovery",
        "runtime_loaded",
    }


def _json_object_columns() -> set[str]:
    return {
        "dependencies",
        "external_provider_defaults",
        "required_system_capabilities",
        "openai_capabilities",
        "default_configuration",
        "parameter_schema",
    }
