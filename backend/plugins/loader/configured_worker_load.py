"""SoAI - Config-aware plugin worker loading [backend/plugins/loader/configured_worker_load.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.plugins.protocols_instance import PluginInstanceProtocol
from core.types.json import JSONDict
from plugins.manager.configuration import reconcile_plugin_configuration
from plugins.package_cache_gc import collect_plugin_package_cache
from plugins.package_preparation import prepare_plugin_package

if TYPE_CHECKING:
    from plugins.loader.preflight import PluginPreflightResult
    from plugins.package_audit import PluginPackageAudit
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = ("ConfiguredPluginWorkerLoad", "load_plugin_worker_with_config")


@dataclass(frozen=True, slots=True)
class ConfiguredPluginWorkerLoad:
    instance: PluginInstanceProtocol
    default_configuration: JSONDict
    parameter_schema: JSONDict


async def load_plugin_worker_with_config(
    *,
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    package_audit: PluginPackageAudit,
    preflight_result: PluginPreflightResult,
    initial_config: JSONDict,
) -> ConfiguredPluginWorkerLoad:
    prepared_package = await prepare_plugin_package(manager, package_audit)
    load_result = await manager.worker_controller.load_plugin(
        plugin_name=plugin_name,
        plugin_package_root=prepared_package.package_root,
        plugin_entrypoint_path=prepared_package.entrypoint_path,
        plugin_file_hash=package_audit.archive_hash,
        package_dependencies=list(preflight_result.dependency_snapshot.package_names),
        plugin_config=dict(initial_config),
    )
    final_instance = load_result.instance
    default_configuration = dict(load_result.surface.default_configuration)
    plugin_specific_config, success = await reconcile_plugin_configuration(
        manager,
        plugin_name,
        default_configuration,
        parameter_schema=dict(load_result.surface.parameter_schema),
    )
    if not success:
        raise StateError("Failed to create or load plugin configuration.")
    resolved_config = plugin_specific_config or {}
    if resolved_config != initial_config:
        load_result = await manager.worker_controller.load_plugin(
            plugin_name=plugin_name,
            plugin_package_root=prepared_package.package_root,
            plugin_entrypoint_path=prepared_package.entrypoint_path,
            plugin_file_hash=package_audit.archive_hash,
            package_dependencies=list(preflight_result.dependency_snapshot.package_names),
            plugin_config=resolved_config,
        )
        final_instance = load_result.instance
        default_configuration = dict(load_result.surface.default_configuration)
    await collect_plugin_package_cache(
        manager,
        plugin_name,
        current_archive_hash=package_audit.archive_hash,
    )
    return ConfiguredPluginWorkerLoad(
        instance=final_instance,
        default_configuration=default_configuration,
        parameter_schema=dict(load_result.surface.parameter_schema),
    )
