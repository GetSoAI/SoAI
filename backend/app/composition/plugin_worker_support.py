"""SoAI - Plugin worker support assembly helpers [backend/app/composition/plugin_worker_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.composition.managed_ipc_worker_factory import ManagedIpcWorkerFactory
from core.bootstrap.venv_paths import get_venv_path, get_venv_python_executable
from core.concurrency.lock_registry import (
    TTLAsyncLockRegistry,
    TTLAsyncLockRegistryDependencies,
)
from core.config.protocols import ConfigProtocol
from core.meta.paths import get_repo_root
from core.plugins.protocols_instance import FilesProtocol
from plugins.environments.baseline import read_plugin_worker_baseline_requirements
from plugins.environments.manager import (
    PluginEnvironmentManager,
    PluginEnvironmentManagerDependencies,
)
from plugins.state.transfer_resolvers import default_plugin_venvs_root_resolver

if TYPE_CHECKING:
    from core.hardware.protocols_storage import StorageManagerProtocol
    from core.runtime.protocols import RuntimeFlagsViewProtocol

__all__ = (
    "PluginWorkerSupport",
    "build_plugin_worker_support",
)


@dataclass(frozen=True, slots=True)
class PluginWorkerSupport:
    environment_manager: PluginEnvironmentManager
    managed_ipc_worker_factory: ManagedIpcWorkerFactory
    lifecycle_locks: TTLAsyncLockRegistry[str]


def build_plugin_worker_support(
    *,
    files: FilesProtocol,
    config: ConfigProtocol,
    storage_manager: StorageManagerProtocol,
    runtime_flags: RuntimeFlagsViewProtocol,
) -> PluginWorkerSupport:
    lifecycle_locks: TTLAsyncLockRegistry[str] = TTLAsyncLockRegistry(
        TTLAsyncLockRegistryDependencies(
            ttl_seconds=7200.0,
            max_size=500,
            cleanup_interval_seconds=600.0,
        ),
    )
    plugin_venvs_root = default_plugin_venvs_root_resolver(files, config)
    environment_manager = PluginEnvironmentManager(
        PluginEnvironmentManagerDependencies(
            plugin_venvs_root=plugin_venvs_root,
            base_python_executable=get_venv_python_executable(get_venv_path(get_repo_root())),
            baseline_requirements=read_plugin_worker_baseline_requirements(),
            storage_manager=storage_manager,
            runtime_flags=runtime_flags,
        ),
    )
    return PluginWorkerSupport(
        environment_manager=environment_manager,
        managed_ipc_worker_factory=ManagedIpcWorkerFactory(),
        lifecycle_locks=lifecycle_locks,
    )
