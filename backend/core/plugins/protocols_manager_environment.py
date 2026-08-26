"""SoAI - Plugin environment manager protocols [backend/core/plugins/protocols_manager_environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

__all__ = (
    "PluginEnvironmentManagerProtocol",
    "PluginEnvironmentProtocol",
)


class PluginEnvironmentProtocol(Protocol):
    plugin_name: str
    env_path: str
    python_executable: str


class PluginEnvironmentManagerProtocol(Protocol):
    def resolve_environment_path(self, plugin_name: str) -> str: ...
    async def ensure_environment(
        self,
        *,
        plugin_name: str,
        package_dependencies: list[str],
    ) -> PluginEnvironmentProtocol: ...
    async def delete_environment(self, plugin_name: str) -> None: ...
