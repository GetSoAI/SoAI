"""SoAI - Plugin dependency assessment indexing [backend/plugins/manifest/dependency_index.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from plugins.manifest.dependency_assessment import (
    PluginDependencyAssessment,
    assess_manifest_dependencies,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "PluginDependencyIndex",
    "build_plugin_dependency_index",
)


@dataclass(frozen=True, slots=True)
class PluginDependencyIndex:
    assessments: dict[str, PluginDependencyAssessment]
    missing_dependencies_by_plugin: dict[str, list[str]]
    declared_dependencies_by_plugin: dict[str, list[str]]
    class_names_by_plugin: dict[str, str | None]
    plugin_names: tuple[str, ...]
    loadable_plugins: set[str]

    def graph_excluding(self, incompatible_plugins: set[str]) -> dict[str, set[str]]:
        plugin_graph: dict[str, set[str]] = {}
        for plugin_name in self.plugin_names:
            if plugin_name in incompatible_plugins:
                continue
            declared_dependencies = self.declared_dependencies_by_plugin.get(plugin_name, [])
            plugin_graph[plugin_name] = {
                dependency_name
                for dependency_name in declared_dependencies
                if dependency_name in self.loadable_plugins and dependency_name != plugin_name
            }
        return plugin_graph


def build_plugin_dependency_index(
    manifests: dict[str, JSONDict],
    *,
    available_plugin_names: set[str] | None = None,
) -> PluginDependencyIndex:
    plugin_names = tuple(manifests.keys())
    loadable_plugins = set(plugin_names)
    dependency_available_names = (
        set(available_plugin_names) if available_plugin_names is not None else loadable_plugins
    )
    assessments: dict[str, PluginDependencyAssessment] = {}
    missing_dependencies_by_plugin: dict[str, list[str]] = {}
    declared_dependencies_by_plugin: dict[str, list[str]] = {}
    class_names_by_plugin: dict[str, str | None] = {}
    for plugin_name, manifest in manifests.items():
        assessment = assess_manifest_dependencies(
            plugin_name,
            manifest,
            available_plugin_names=dependency_available_names,
        )
        assessments[plugin_name] = assessment
        declared_dependencies_by_plugin[plugin_name] = assessment.declared_plugin_dependencies
        class_names_by_plugin[plugin_name] = assessment.class_name
        if assessment.missing_dependencies:
            missing_dependencies_by_plugin[plugin_name] = list(assessment.missing_dependencies)
    return PluginDependencyIndex(
        assessments=assessments,
        missing_dependencies_by_plugin=missing_dependencies_by_plugin,
        declared_dependencies_by_plugin=declared_dependencies_by_plugin,
        class_names_by_plugin=class_names_by_plugin,
        plugin_names=plugin_names,
        loadable_plugins=loadable_plugins,
    )
