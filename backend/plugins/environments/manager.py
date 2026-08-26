"""SoAI - Per-plugin Python environment manager [backend/plugins/environments/manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies
from core.errors.exceptions import ProcessError, ValidationError
from core.filesystem.async_queries import async_makedirs
from core.plugins.protocols_manager_environment import PluginEnvironmentProtocol
from core.runtime.network_policy import require_online_mode
from plugins.environments.commands import (
    delete_plugin_environment_path,
    ensure_plugin_environment_python,
    install_plugin_environment_requirements,
    query_plugin_environment_freeze,
    resolve_plugin_environment_python,
)
from plugins.environments.metadata import (
    PluginEnvironmentIdentity,
    build_plugin_environment_metadata,
    environment_freeze_matches,
    environment_metadata_matches,
    read_plugin_environment_metadata,
    write_plugin_environment_metadata,
)
from plugins.environments.paths import resolve_plugin_environment_path
from plugins.environments.requirements import normalize_plugin_requirements

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "PluginEnvironment",
    "PluginEnvironmentManager",
    "PluginEnvironmentManagerDependencies",
)


@dataclass(slots=True)
class PluginEnvironment:
    plugin_name: str
    env_path: str
    python_executable: str


@dataclass(frozen=True, slots=True)
class PluginEnvironmentManagerDependencies:
    plugin_venvs_root: str
    base_python_executable: str
    baseline_requirements: tuple[str, ...]
    storage_manager: StorageManagerProtocol
    runtime_flags: RuntimeFlagsViewProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginEnvironmentManagerDependencies",
            plugin_venvs_root=self.plugin_venvs_root,
            base_python_executable=self.base_python_executable,
            baseline_requirements=self.baseline_requirements,
            storage_manager=self.storage_manager,
            runtime_flags=self.runtime_flags,
        )


class PluginEnvironmentManager:
    def __init__(self, deps: PluginEnvironmentManagerDependencies) -> None:
        self._plugin_venvs_root = deps.plugin_venvs_root
        self._base_python_executable = deps.base_python_executable
        self._baseline_requirements = deps.baseline_requirements
        self._storage_manager = deps.storage_manager
        self._runtime_flags = deps.runtime_flags
        self._environment_locks: dict[str, asyncio.Lock] = {}

    def resolve_environment_path(self, plugin_name: str) -> str:
        return resolve_plugin_environment_path(self._plugin_venvs_root, plugin_name)

    async def ensure_environment(
        self,
        *,
        plugin_name: str,
        package_dependencies: list[str],
    ) -> PluginEnvironmentProtocol:
        env_path = self.resolve_environment_path(plugin_name)
        async with self._lock_for_plugin(plugin_name):
            normalized_requirements = tuple(normalize_plugin_requirements(package_dependencies))
            identity = PluginEnvironmentIdentity(
                plugin_name=plugin_name,
                worker_baseline_requirements=self._baseline_requirements,
                package_dependencies=normalized_requirements,
            )
            try:
                metadata = read_plugin_environment_metadata(env_path)
            except (OSError, ValidationError):
                metadata = None
            python_executable = resolve_plugin_environment_python(env_path)
            metadata_matches = environment_metadata_matches(metadata, identity)
            freeze_matches = False
            if metadata_matches and os.path.isfile(python_executable):
                try:
                    current_freeze = await query_plugin_environment_freeze(python_executable)
                    freeze_matches = environment_freeze_matches(metadata, current_freeze)
                except ProcessError:
                    freeze_matches = False
            if not metadata_matches or not freeze_matches:
                require_online_mode(
                    self._runtime_flags,
                    source="plugin environment provisioning",
                )
                await async_makedirs(os.path.dirname(env_path), exist_ok=True)
                await delete_plugin_environment_path(env_path)
                python_executable = await ensure_plugin_environment_python(
                    env_path,
                    self._base_python_executable,
                )
                await install_plugin_environment_requirements(
                    python_executable,
                    self._baseline_requirements,
                    normalized_requirements,
                )
                freeze = await query_plugin_environment_freeze(python_executable)
                write_plugin_environment_metadata(
                    env_path,
                    build_plugin_environment_metadata(identity, pip_freeze_all=freeze),
                    self._storage_manager,
                )
            return PluginEnvironment(
                plugin_name=plugin_name,
                env_path=env_path,
                python_executable=python_executable,
            )

    async def delete_environment(self, plugin_name: str) -> None:
        env_path = self.resolve_environment_path(plugin_name)
        async with self._lock_for_plugin(plugin_name):
            await delete_plugin_environment_path(env_path)

    def _lock_for_plugin(self, plugin_name: str) -> asyncio.Lock:
        lock = self._environment_locks.get(plugin_name)
        if lock is None:
            lock = asyncio.Lock()
            self._environment_locks[plugin_name] = lock
        return lock
