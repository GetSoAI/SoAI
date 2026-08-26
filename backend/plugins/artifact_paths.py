"""SoAI - Plugin artifact path and hash helpers [backend/plugins/artifact_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.filesystem.hashing import calculate_file_hash
from plugins.path_safety import get_plugin_file_path, get_plugin_validation_cache_path
from plugins.protocols_internal.runtime.internal_protocols import (
    PluginManagerRuntimeProtocol,
)

__all__ = (
    "collect_plugin_artifact_paths",
    "collect_plugin_validation_cache_paths",
    "get_plugin_file_hash",
)


def collect_plugin_validation_cache_paths(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> tuple[str, str]:
    validation_cache_path = get_plugin_validation_cache_path(manager, plugin_name)
    validation_cache_lock_path = manager.dependencies.infrastructure.config_manager.get_lock_path(
        validation_cache_path,
    )
    return (validation_cache_path, validation_cache_lock_path)


def collect_plugin_artifact_paths(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> list[str]:
    plugin_file_path = get_plugin_file_path(manager, plugin_name)
    config_file_path = manager.dependencies.infrastructure.config_manager.get_config_path_sync(
        plugin_name,
    )
    validation_cache_paths = collect_plugin_validation_cache_paths(manager, plugin_name)
    return [
        plugin_file_path,
        config_file_path,
        manager.dependencies.infrastructure.config_manager.get_lock_path(config_file_path),
        f"{config_file_path}.backup",
        *validation_cache_paths,
    ]


async def get_plugin_file_hash(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    plugin_file_path: str | None = None,
) -> str | None:
    resolved_path = plugin_file_path or get_plugin_file_path(manager, plugin_name)
    exists = await asyncio.to_thread(os.path.exists, resolved_path)
    if not exists:
        return None
    return await calculate_file_hash(resolved_path)
