"""SoAI - Shared model catalog plugin borrowing [backend/plugins/manager/catalog_reads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import StateError
from core.plugins.protocols_instance import PluginInstanceProtocol
from plugins.protocols_internal.runtime.internal_protocols import PluginManagerRuntimeProtocol
from plugins.protocols_internal.state.catalog_reads import PluginCatalogReadState

__all__ = ("borrow_model_catalog_plugin",)

CATALOG_ACQUISITION_ATTEMPTS = 2


@asynccontextmanager
async def borrow_model_catalog_plugin(
    manager: PluginManagerRuntimeProtocol, plugin_name: str
) -> AsyncGenerator[PluginInstanceProtocol]:
    for _attempt in range(CATALOG_ACQUISITION_ATTEMPTS):
        discovery_owned = await manager.get_plugin_instance(plugin_name) is None
        instance = await manager.require_loaded_plugin(plugin_name, auto_load=True)
        identity = id(instance)
        async with manager.state.locks.load_lock:
            if manager.state.catalog.loaded_plugin_instances.get(plugin_name) is not instance:
                continue
            if identity not in manager.state.catalog.model_catalog_reads:
                manager.state.catalog.model_catalog_reads[identity] = PluginCatalogReadState()
            read = manager.state.catalog.model_catalog_reads[identity]
            read.users += 1
            read.discovery_owned = read.discovery_owned or discovery_owned
            break
    else:
        raise StateError("The plugin runtime repeatedly changed while preparing model search.")
    try:
        yield instance
    finally:
        await uncancel_then_cleanup(_release_catalog_reader(manager, plugin_name, instance, read))


async def _release_catalog_reader(
    manager: PluginManagerRuntimeProtocol,
    plugin_name: str,
    instance: PluginInstanceProtocol,
    read: PluginCatalogReadState,
) -> None:
    identity = id(instance)
    async with manager.state.locks.load_lock:
        read.users -= 1
        release = read.users == 0 and read.discovery_owned
        if read.users == 0 and not read.discovery_owned:
            manager.state.catalog.model_catalog_reads.pop(identity, None)
    if release:
        await manager.release_discovery_plugin_instance(plugin_name, expected_instance=instance)
        async with manager.state.locks.load_lock:
            if read.users == 0 and manager.state.catalog.model_catalog_reads.get(identity) is read:
                manager.state.catalog.model_catalog_reads.pop(identity)
