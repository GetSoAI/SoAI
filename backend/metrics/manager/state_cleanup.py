"""SoAI - Metrics state cleanup routines [backend/metrics/manager/state_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.logging.protocols import LoggerProtocol
from metrics.manager.plugin_cleanup import (
    collect_active_plugin_names,
    prune_deleted_plugin_scoped_metrics,
)
from metrics.manager.pruning import prune_unique_items

if TYPE_CHECKING:
    from core.plugins.protocols_database import DatabasePluginsProtocol
    from metrics.manager.types import MetricsTree

__all__ = (
    "cleanup_metrics_state",
    "prune_deleted_plugin_metrics",
)


async def prune_deleted_plugin_metrics(
    *,
    lock: asyncio.Lock,
    metrics_ref: list[MetricsTree],
    database_plugins: DatabasePluginsProtocol,
    logger: LoggerProtocol,
) -> None:
    plugin_records = await database_plugins.get_all_plugins()
    active_plugins = collect_active_plugin_names(plugin_records)
    async with lock:
        removed_keys = prune_deleted_plugin_scoped_metrics(metrics_ref[0], active_plugins)
    if removed_keys > 0:
        logger.debug("Pruned %s stale plugin-scoped metric key(s).", removed_keys)


async def cleanup_metrics_state(
    *,
    lock: asyncio.Lock,
    metrics_ref: list[MetricsTree],
    database_plugins: DatabasePluginsProtocol,
    logger: LoggerProtocol,
) -> None:
    await prune_unique_items(lock, metrics_ref[0])
    await prune_deleted_plugin_metrics(
        lock=lock,
        metrics_ref=metrics_ref,
        database_plugins=database_plugins,
        logger=logger,
    )
