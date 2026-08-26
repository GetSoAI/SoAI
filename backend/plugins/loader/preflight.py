"""SoAI - Plugin safety, dependency, and compatibility preflight checks [backend/plugins/loader/preflight.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.logging.trace import get_logger
from core.plugins.errors import PluginIncompatibleError
from core.state.compatibility import CompatibilityInfo
from plugins.class_validation import validate_plugin_safety
from plugins.manifest.dependency_assessment import (
    build_missing_dependency_compatibility,
)
from plugins.manifest.dependency_index import build_plugin_dependency_index
from plugins.manifest.dependency_snapshot import (
    PluginDependencySnapshot,
    dependency_snapshot_from_manifest,
)
from plugins.manifest.reader import read_plugin_manifests_from_disk
from plugins.package_audit import audit_plugin_package
from plugins.state.compatibility import should_block_for_incompatibility
from plugins.state.manifest_compatibility import check_plugin_manifest_compatibility

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from plugins.package_audit import PluginPackageAudit
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = (
    "PluginPreflightResult",
    "perform_plugin_preflight_checks",
)

LOGGER_NAME = "SoAI.plugins.loader.preflight"


@dataclass(frozen=True, slots=True)
class PluginPreflightResult:
    compatibility: CompatibilityInfo
    existing_record: JSONDict | None
    manifest: JSONDict
    dependency_snapshot: PluginDependencySnapshot
    package_audit: PluginPackageAudit


async def perform_plugin_preflight_checks(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    package_audit: PluginPackageAudit | None = None,
    manifest: JSONDict | None = None,
    dependency_manifests: dict[str, JSONDict] | None = None,
) -> PluginPreflightResult:
    logger = get_logger(LOGGER_NAME)
    if package_audit is None:
        package_audit = await audit_plugin_package(
            manager,
            plugin_name,
            enforce_import_scan=False,
            enforce_hash_policy=True,
        )
    safety_validation_enabled = manager.dependencies.core.config.get(
        "PLUGINS.SECURITY.SAFETY_VALIDATION",
        True,
    )
    if safety_validation_enabled:
        is_safe, reason = await validate_plugin_safety(
            manager,
            plugin_name,
            package_audit=package_audit,
        )
        if not is_safe:
            raise StateError(f"Plugin '{plugin_name}' failed safety validation: {reason}")
        logger.debug("Plugin '%s' passed safety validation: %s", plugin_name, reason)
    if manifest is None:
        manifest_map = await read_plugin_manifests_from_disk(
            manager,
            [plugin_name],
            enforce_safety_validation=not safety_validation_enabled,
            package_audits={plugin_name: package_audit},
        )
        manifest = manifest_map.get(plugin_name)
    if not isinstance(manifest, dict):
        raise StateError(f"Plugin '{plugin_name}' manifest could not be read for preflight checks.")
    dependency_snapshot = dependency_snapshot_from_manifest(manifest)
    if dependency_manifests is None:
        dependency_manifests = {plugin_name: manifest}
        dependency_names = [
            dependency_name
            for dependency_name in dependency_snapshot.plugin_names
            if dependency_name != plugin_name
        ]
        dependency_manifests.update(
            await read_plugin_manifests_from_disk(
                manager,
                dependency_names,
            ),
        )
    dependency_index = build_plugin_dependency_index(
        {plugin_name: manifest},
        available_plugin_names=set(dependency_manifests.keys()),
    )
    dependency_assessment = dependency_index.assessments[plugin_name]
    dependency_snapshot = dependency_assessment.snapshot
    if dependency_assessment.missing_dependencies:
        compatibility = build_missing_dependency_compatibility(dependency_assessment)
        raise PluginIncompatibleError(
            plugin_name,
            compatibility,
            plugin_class=None,
            plugin_class_name=None,
        )
    existing_record = await manager.dependencies.databases.plugins.get_plugin_by_name(plugin_name)
    compatibility = await check_plugin_manifest_compatibility(
        plugin_name,
        manifest,
        manager.state.configuration.core_version,
        manager.dependencies.infrastructure.hardware_helpers.get_gpu_info,
        existing_record,
    )
    should_block, is_hw_block = should_block_for_incompatibility(
        compatibility,
        existing_record,
        manager.policy.hardware_incompatible_reasons,
    )
    if should_block and (not is_hw_block):
        raise PluginIncompatibleError(
            plugin_name,
            compatibility,
            plugin_class=None,
            plugin_class_name=None,
        )
    return PluginPreflightResult(
        compatibility=compatibility,
        existing_record=existing_record,
        manifest=manifest,
        dependency_snapshot=dependency_snapshot,
        package_audit=package_audit,
    )
