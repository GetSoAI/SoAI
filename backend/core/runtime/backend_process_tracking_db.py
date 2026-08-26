"""SoAI - DB-backed backend process identity cleanup helpers [backend/core/runtime/backend_process_tracking_db.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.runtime.backend_process_tracking import (
    BackendProcessCleanupResult,
    BackendProcessIdentity,
    backend_process_identities_to_json_dicts,
    cleanup_backend_process_identities,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.plugins.protocols_database import DatabasePluginsProtocol

__all__ = (
    "BackendProcessDatabaseCleanupFailure",
    "cleanup_all_tracked_backend_processes_from_database",
    "cleanup_tracked_backend_processes_from_database",
)


@dataclass(frozen=True, slots=True)
class BackendProcessDatabaseCleanupFailure:
    plugin_name: str
    failed: list[BackendProcessIdentity]

    @property
    def failed_payload(self) -> list[dict[str, int]]:
        return backend_process_identities_to_json_dicts(self.failed)


async def cleanup_tracked_backend_processes_from_database(
    database_plugins: DatabasePluginsProtocol,
    *,
    plugin_name: str,
    logger: LoggerProtocol,
    prune_on_failure: bool = True,
) -> BackendProcessCleanupResult | None:
    identities = await database_plugins.get_runtime_processes(plugin_name)
    if not identities:
        return None
    cleanup_result = await cleanup_backend_process_identities(
        identities,
        plugin_name=plugin_name,
        logger=logger,
    )
    if cleanup_result.succeeded:
        await database_plugins.clear_runtime_processes(plugin_name)
        return cleanup_result
    if prune_on_failure:
        await database_plugins.set_runtime_processes(
            plugin_name,
            cleanup_result.failed,
        )
    return cleanup_result


async def cleanup_all_tracked_backend_processes_from_database(
    database_plugins: DatabasePluginsProtocol,
    *,
    logger: LoggerProtocol,
) -> list[BackendProcessDatabaseCleanupFailure]:
    failures: list[BackendProcessDatabaseCleanupFailure] = []
    tracked_plugins = await database_plugins.list_plugins_with_runtime_processes()
    for record in tracked_plugins:
        plugin_name = record["plugin_name"]
        identities = record["runtime_processes"]
        cleanup_result = await cleanup_backend_process_identities(
            identities,
            plugin_name=plugin_name,
            logger=logger,
        )
        if cleanup_result.succeeded:
            await database_plugins.clear_runtime_processes(plugin_name)
            continue
        await database_plugins.set_runtime_processes(
            plugin_name,
            cleanup_result.failed,
        )
        failures.append(
            BackendProcessDatabaseCleanupFailure(
                plugin_name=plugin_name,
                failed=cleanup_result.failed,
            ),
        )
    return failures
