"""SoAI - Shared metrics path traversal and mutation [backend/metrics/manager/path_updates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from metrics.manager.types import MetricsTree, MetricValue

if TYPE_CHECKING:
    type ParentMap = dict[str, MetricValue]

__all__ = ("apply_metric_update",)

LOGGER_NAME = "SoAI.metrics.manager.path_updates"


def traverse_to_parent(
    metrics: MetricsTree,
    keys: tuple[str, ...],
) -> ParentMap | None:
    node: MetricValue = metrics
    for key in keys[:-1]:
        if not isinstance(node, dict):
            return None
        try:
            node = node[key]
        except (KeyError, TypeError):
            return None
    return node if isinstance(node, dict) else None


async def apply_metric_update(
    lock: asyncio.Lock,
    metrics: MetricsTree,
    keys: tuple[str, ...],
    missing_message: str,
    updater: Callable[[ParentMap, str], None],
) -> None:
    logger = get_logger(LOGGER_NAME)
    async with lock:
        parent = traverse_to_parent(metrics, keys)
        if parent is None:
            logger.warning(missing_message)
            return
        updater(parent, keys[-1])
