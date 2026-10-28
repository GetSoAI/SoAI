"""SoAI - Ordered plugin and model catalog locking [backend/models/catalog_locking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterable
from contextlib import AsyncExitStack, asynccontextmanager

from core.concurrency.protocols import AsyncLockRegistryProtocol
from core.plugins.protocols_lifecycle import PluginLifecycleProtocol


async def enter_plugin_lifecycle_locks(
    exit_stack: AsyncExitStack,
    plugin_lifecycle: PluginLifecycleProtocol,
    plugin_names: Iterable[str],
) -> None:
    for plugin_name in sorted(set(plugin_names)):
        await exit_stack.enter_async_context(
            plugin_lifecycle.plugin_lock_scope(plugin_name),
        )


async def enter_model_record_locks(
    exit_stack: AsyncExitStack,
    model_record_locks: AsyncLockRegistryProtocol[str],
    universal_ids: Iterable[str],
) -> None:
    for universal_id in sorted(set(universal_ids)):
        await exit_stack.enter_async_context(model_record_locks[universal_id])


@asynccontextmanager
async def catalog_mutation_lock_scope(
    plugin_lifecycle: PluginLifecycleProtocol,
    model_record_locks: AsyncLockRegistryProtocol[str],
    plugin_names: Iterable[str],
    universal_ids: Iterable[str],
) -> AsyncGenerator[None]:
    async with AsyncExitStack() as exit_stack:
        await enter_plugin_lifecycle_locks(exit_stack, plugin_lifecycle, plugin_names)
        await enter_model_record_locks(exit_stack, model_record_locks, universal_ids)
        yield


__all__ = (
    "catalog_mutation_lock_scope",
    "enter_model_record_locks",
    "enter_plugin_lifecycle_locks",
)
