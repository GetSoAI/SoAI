"""SoAI - Lease-aware plugin package cache garbage collection [backend/plugins/package_cache_gc.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.files.locking import async_guarded_file_lock
from core.files.managed_file_deletion import delete_managed_path
from core.serialization.sha256_hexdigest import is_canonical_sha256_hexdigest
from core.validation.identifiers import is_identifier_strictly_alnum
from plugins.package_completion import read_plugin_package_completion_record
from plugins.package_leases import list_live_plugin_package_leases
from plugins.package_paths import (
    get_plugin_package_cache_directory,
    get_plugin_package_cache_lock_target,
    get_plugin_package_hash_lock_target,
    get_plugin_package_lease_directory,
)

if TYPE_CHECKING:
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginManagerRuntimeProtocol,
    )

__all__ = (
    "collect_plugin_package_cache",
    "collect_plugin_package_caches",
    "remove_plugin_package_cache",
)


def _completion_matches_hash(package_path: str, archive_hash: str) -> bool:
    completion = read_plugin_package_completion_record(package_path)
    return completion is not None and completion.archive_hash == archive_hash


async def collect_plugin_package_cache(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    *,
    current_archive_hash: str | None,
) -> None:
    cache_directory = get_plugin_package_cache_directory(
        manager.paths.temp_directory,
        plugin_name,
    )
    config_manager = manager.dependencies.infrastructure.config_manager
    cache_lock_path = config_manager.get_lock_path(
        get_plugin_package_cache_lock_target(
            manager.paths.temp_directory,
            plugin_name,
        )
    )
    os.makedirs(os.path.dirname(cache_lock_path), exist_ok=True)
    async with async_guarded_file_lock(cache_lock_path, timeout=120):
        packages_root = os.path.dirname(cache_directory)
        if os.path.islink(packages_root) or (
            os.path.lexists(packages_root) and not os.path.isdir(packages_root)
        ):
            await delete_managed_path(manager.paths.temp_directory, packages_root)
            return
        if os.path.islink(cache_directory) or (
            os.path.lexists(cache_directory) and not os.path.isdir(cache_directory)
        ):
            await delete_managed_path(manager.paths.temp_directory, cache_directory)
            return
        live_hashes = {
            lease.archive_hash
            for lease in await asyncio.to_thread(
                list_live_plugin_package_leases,
                manager.paths.temp_directory,
                plugin_name,
            )
        }
        try:
            entries = sorted(os.listdir(cache_directory))
        except FileNotFoundError:
            return
        for entry in entries:
            if entry.endswith(".lock"):
                continue
            entry_path = os.path.join(cache_directory, entry)
            archive_hash = entry
            if entry.startswith(".staging."):
                components = entry.split(".")
                archive_hash = components[2] if len(components) > 2 else ""
            hash_lock_value = (
                archive_hash if is_canonical_sha256_hexdigest(archive_hash) else "0" * 64
            )
            hash_lock_path = config_manager.get_lock_path(
                get_plugin_package_hash_lock_target(
                    manager.paths.temp_directory,
                    plugin_name,
                    hash_lock_value,
                )
            )
            async with async_guarded_file_lock(hash_lock_path, timeout=120):
                if entry.startswith(".staging."):
                    await delete_managed_path(manager.paths.temp_directory, entry_path)
                    continue
                complete = await asyncio.to_thread(
                    _completion_matches_hash,
                    entry_path,
                    archive_hash,
                )
                if archive_hash in live_hashes:
                    continue
                if complete and archive_hash == current_archive_hash:
                    continue
                await delete_managed_path(manager.paths.temp_directory, entry_path)


def _list_cached_plugin_directories(packages_root: str) -> set[str]:
    try:
        with os.scandir(packages_root) as entries:
            return {
                entry.name
                for entry in entries
                if entry.is_dir(follow_symlinks=False)
                and not entry.name.startswith("_")
                and is_identifier_strictly_alnum(entry.name)
            }
    except FileNotFoundError:
        return set()


async def collect_plugin_package_caches(
    manager: PluginManagerRuntimeProtocol,
    current_archive_hashes: dict[str, str],
) -> None:
    packages_root = os.path.join(manager.paths.temp_directory, "plugin_packages")
    cached_plugins = await asyncio.to_thread(
        _list_cached_plugin_directories,
        packages_root,
    )
    plugin_names = cached_plugins.union(current_archive_hashes)
    for plugin_name in sorted(plugin_names):
        await collect_plugin_package_cache(
            manager,
            plugin_name,
            current_archive_hash=current_archive_hashes.get(plugin_name),
        )


async def remove_plugin_package_cache(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
) -> None:
    cache_directory = get_plugin_package_cache_directory(
        manager.paths.temp_directory,
        plugin_name,
    )
    lease_directory = get_plugin_package_lease_directory(
        manager.paths.temp_directory,
        plugin_name,
    )
    lock_path = manager.dependencies.infrastructure.config_manager.get_lock_path(
        get_plugin_package_cache_lock_target(
            manager.paths.temp_directory,
            plugin_name,
        )
    )
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    async with async_guarded_file_lock(lock_path, timeout=120):
        packages_root = os.path.dirname(cache_directory)
        if os.path.islink(packages_root) or (
            os.path.lexists(packages_root) and not os.path.isdir(packages_root)
        ):
            await delete_managed_path(manager.paths.temp_directory, packages_root)
        live_leases = await asyncio.to_thread(
            list_live_plugin_package_leases,
            manager.paths.temp_directory,
            plugin_name,
        )
        if live_leases:
            raise StateError(
                f"Cannot delete plugin package cache for '{plugin_name}' while a worker lease is live.",
            )
        await delete_managed_path(manager.paths.temp_directory, cache_directory)
        await delete_managed_path(manager.paths.temp_directory, lease_directory)
