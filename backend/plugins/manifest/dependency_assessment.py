"""SoAI - Plugin manifest dependency assessment [backend/plugins/manifest/dependency_assessment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.state.compatibility import CompatibilityInfo, IncompatibilityReason
from plugins.manifest.dependency_snapshot import (
    PluginDependencySnapshot,
    dependency_snapshot_from_manifest,
    missing_plugin_dependencies,
)
from plugins.state.capability_normalization import as_json_list
from plugins.state.compatibility import build_compatibility_info

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "PluginDependencyAssessment",
    "assess_manifest_dependencies",
    "build_missing_dependency_compatibility",
    "build_missing_dependency_plugin_data",
)


@dataclass(frozen=True, slots=True)
class PluginDependencyAssessment:
    plugin_name: str
    manifest: JSONDict
    snapshot: PluginDependencySnapshot
    declared_plugin_dependencies: list[str]
    package_dependencies: list[str]
    missing_dependencies: list[str]
    class_name: str | None


def _read_manifest_class_name(manifest: JSONDict) -> str | None:
    class_value = manifest.get("class_name")
    if isinstance(class_value, str) and class_value.strip():
        return class_value.strip()
    return None


def assess_manifest_dependencies(
    plugin_name: str,
    manifest: JSONDict,
    *,
    available_plugin_names: set[str],
) -> PluginDependencyAssessment:
    snapshot = dependency_snapshot_from_manifest(manifest)
    declared_plugin_dependencies = list(snapshot.plugin_names)
    package_dependencies = list(snapshot.package_names)
    missing_dependencies = missing_plugin_dependencies(
        snapshot,
        available_plugin_names=available_plugin_names,
        plugin_name=plugin_name,
    )
    return PluginDependencyAssessment(
        plugin_name=plugin_name,
        manifest=manifest,
        snapshot=snapshot,
        declared_plugin_dependencies=declared_plugin_dependencies,
        package_dependencies=package_dependencies,
        missing_dependencies=missing_dependencies,
        class_name=_read_manifest_class_name(manifest),
    )


def build_missing_dependency_compatibility(
    assessment: PluginDependencyAssessment,
) -> CompatibilityInfo:
    missing_dependency_names = ", ".join(sorted(assessment.missing_dependencies))
    return build_compatibility_info(
        IncompatibilityReason.DEPENDENCY_MISSING,
        f"Missing required plugin dependencies: {missing_dependency_names}.",
        {
            "missing_dependencies": as_json_list(sorted(assessment.missing_dependencies)),
            "declared_dependencies": as_json_list(
                sorted(set(assessment.declared_plugin_dependencies)),
            ),
        },
        False,
    )


def build_missing_dependency_plugin_data(
    assessment: PluginDependencyAssessment,
) -> JSONDict:
    plugin_data = dict(assessment.manifest)
    plugin_data["plugin_name"] = assessment.plugin_name
    name_value = plugin_data.get("name")
    plugin_data["name"] = (
        name_value.strip()
        if isinstance(name_value, str) and name_value.strip()
        else assessment.plugin_name
    )
    return plugin_data
