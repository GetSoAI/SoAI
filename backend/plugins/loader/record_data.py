"""SoAI - Plugin record payload construction for persistence [backend/plugins/loader/record_data.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.filesystem.async_queries import async_path_exists
from core.serialization.json_parsing import parse_json_value
from core.timing.epoch import epoch_ms
from core.types.json_value import coerce_json_dict
from plugins.artifact_paths import get_plugin_file_hash
from plugins.identity import normalize_plugin_display_name
from plugins.loader.manifest_repair import recover_plugin_manifest_override
from plugins.path_safety import get_plugin_file_path

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from plugins.package_audit import PluginPackageAudit
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("build_plugin_record_data",)


async def _read_existing_parameter_schema(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    expected_archive_hash: str | None,
) -> JSONDict | None:
    existing_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    if existing_record is None:
        return None
    if (
        expected_archive_hash is not None
        and existing_record.get("file_hash") != expected_archive_hash
    ):
        return None
    raw_schema = existing_record.get("parameter_schema")
    if isinstance(raw_schema, str) and raw_schema.strip():
        return coerce_json_dict(
            parse_json_value(raw_schema, field="plugins_catalog.parameter_schema"),
        )
    return coerce_json_dict(raw_schema)


async def build_plugin_record_data(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    plugin_data_override: JSONDict | None = None,
    package_audit: PluginPackageAudit | None = None,
    operation: str | None = None,
    error_message: str | None = None,
) -> JSONDict:
    if plugin_data_override is not None:
        plugin_data = dict(plugin_data_override)
    else:
        if operation is None or error_message is None:
            raise StateError(
                f"Cannot build persisted plugin data for '{plugin_name}' without manifest recovery context.",
            )
        recovered_plugin_data, manifest_error = await recover_plugin_manifest_override(
            manager,
            plugin_name,
            operation=operation,
            error_message=error_message,
        )
        if recovered_plugin_data is None:
            raise StateError(
                f"Cannot persist plugin data for '{plugin_name}': manifest could not be read.",
            ) from manifest_error
        plugin_data = recovered_plugin_data
    plugin_data["plugin_name"] = plugin_name
    plugin_data["name"] = normalize_plugin_display_name(plugin_name, plugin_data)
    if "default_configuration" not in plugin_data:
        plugin_data["default_configuration"] = {}
    parameter_schema_value = plugin_data.get("parameter_schema")
    if not isinstance(parameter_schema_value, dict) or not parameter_schema_value:
        plugin_data["parameter_schema"] = (
            await _read_existing_parameter_schema(
                manager,
                plugin_name,
                expected_archive_hash=(
                    package_audit.content.archive_hash if package_audit is not None else None
                ),
            )
            or {}
        )
    if "backend_variant_options" not in plugin_data:
        plugin_data["backend_variant_options"] = []
    if "supports_model_search" not in plugin_data:
        plugin_data["supports_model_search"] = False
    if "supports_model_variant_discovery" not in plugin_data:
        plugin_data["supports_model_variant_discovery"] = False
    if "supports_gpu_binding" not in plugin_data:
        plugin_data["supports_gpu_binding"] = False
    if "runtime_loaded" not in plugin_data:
        plugin_data["runtime_loaded"] = False
    if "backend_status" not in plugin_data:
        plugin_data["backend_status"] = None
    plugin_data["catalog_reconciled_at_ms"] = epoch_ms()
    if package_audit is not None:
        plugin_data["file_path"] = package_audit.archive_path
        plugin_data["file_hash"] = package_audit.content.archive_hash
        return plugin_data
    plugin_file_path = get_plugin_file_path(manager, plugin_name)
    if await async_path_exists(plugin_file_path):
        plugin_data["file_path"] = plugin_file_path
        if not plugin_data.get("file_hash"):
            plugin_data["file_hash"] = await get_plugin_file_hash(
                manager,
                plugin_name,
                plugin_file_path=plugin_file_path,
            )
    else:
        plugin_data["file_path"] = None
        plugin_data["file_hash"] = None
    return plugin_data
