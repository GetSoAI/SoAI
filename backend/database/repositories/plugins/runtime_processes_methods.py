"""SoAI - Database plugin runtime process tracking methods [backend/database/repositories/plugins/runtime_processes_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from database.repositories.plugins.internal_protocols import (
    DatabasePluginsRuntimeProcessesSurface,
)
from database.repositories.plugins.runtime_processes import (
    get_runtime_processes_query,
    list_plugins_with_runtime_processes_query,
    sync_clear_runtime_processes,
    sync_set_runtime_processes,
)

if TYPE_CHECKING:
    from core.plugins.protocols_database import PluginRuntimeProcessesPayload
    from core.runtime.backend_process_tracking import BackendProcessIdentity

__all__ = (
    "clear_runtime_processes_method",
    "get_runtime_processes_method",
    "list_plugins_with_runtime_processes_method",
    "set_runtime_processes_method",
)


async def get_runtime_processes_method(
    self: DatabasePluginsRuntimeProcessesSurface,
    plugin_name: str,
) -> list[BackendProcessIdentity]:
    return await self.core.reader.execute_read(get_runtime_processes_query, plugin_name)


async def set_runtime_processes_method(
    self: DatabasePluginsRuntimeProcessesSurface,
    plugin_name: str,
    identities: list[BackendProcessIdentity],
) -> None:
    await self.core.writer.queue_write_operation(
        sync_set_runtime_processes,
        plugin_name,
        identities,
    )


async def clear_runtime_processes_method(
    self: DatabasePluginsRuntimeProcessesSurface,
    plugin_name: str,
) -> None:
    await self.core.writer.queue_write_operation(
        sync_clear_runtime_processes,
        plugin_name,
    )


async def list_plugins_with_runtime_processes_method(
    self: DatabasePluginsRuntimeProcessesSurface,
) -> list[PluginRuntimeProcessesPayload]:
    return await self.core.reader.execute_read(list_plugins_with_runtime_processes_query)
