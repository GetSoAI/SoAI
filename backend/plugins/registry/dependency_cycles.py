"""SoAI - Plugin dependency cycle parsing helpers [backend/plugins/registry/dependency_cycles.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from plugins.state.capability_normalization import as_json_list

__all__ = (
    "as_json_list",
    "get_cyclic_plugins",
)


def get_cyclic_plugins(error_message: str, plugin_graph: dict[str, set[str]]) -> set[str]:
    cyclic_plugins: set[str] = set()
    if "Circular dependency" in error_message:
        match = re.search("involving plugin: (\\S+)", error_message)
        if match:
            cyclic_plugins.add(match.group(1))
    elif "unresolved dependency" in error_message:
        match = re.search("Plugin '(\\S+)' has an unresolved dependency", error_message)
        if match:
            cyclic_plugins.add(match.group(1))
    if not cyclic_plugins:
        return cyclic_plugins
    changed = True
    while changed:
        changed = False
        for plugin_name, dependencies in plugin_graph.items():
            if plugin_name not in cyclic_plugins and dependencies & cyclic_plugins:
                cyclic_plugins.add(plugin_name)
                changed = True
    return cyclic_plugins
