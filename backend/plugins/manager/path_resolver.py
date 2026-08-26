"""SoAI - Plugin manager path resolution [backend/plugins/manager/path_resolver.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.plugins.protocols_manager_dependencies import PluginManagerPathsProtocol
from plugins.manager.dependencies import PluginManagerDependencies, PluginManagerPaths

__all__ = ("resolve_plugin_manager_paths",)


def resolve_plugin_manager_paths(
    deps: PluginManagerDependencies,
) -> PluginManagerPathsProtocol:
    plugin_directory_abs, backends_directory_abs, plugin_directory_real = deps.plugin_path_resolver(
        deps.plugin_directory,
        deps.backends_directory,
    )
    temp_directory = deps.temp_directory_resolver(deps.core.files, deps.core.config)
    plugin_venvs_root = deps.plugin_venvs_root_resolver(deps.core.files, deps.core.config)
    return PluginManagerPaths(
        plugin_directory=plugin_directory_abs,
        backends_directory=backends_directory_abs,
        plugin_directory_real=plugin_directory_real,
        temp_directory=temp_directory,
        plugin_venvs_root=plugin_venvs_root,
    )
