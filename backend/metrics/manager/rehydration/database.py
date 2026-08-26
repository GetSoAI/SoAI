"""SoAI - Metrics rehydration from database persistence [backend/metrics/manager/rehydration/database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.metrics.protocols import DatabaseMetricsProtocol
from metrics.manager.rehydration.records import rehydrate_metrics_from_records

if TYPE_CHECKING:
    from metrics.manager.types import MetricsTree

__all__ = ("rehydrate_from_database",)

LOGGER_NAME = "SoAI.metrics.manager.database"


async def rehydrate_from_database(
    lock: asyncio.Lock,
    metrics_ref: list[MetricsTree],
    session_start_time_ms: int,
    database_metrics: DatabaseMetricsProtocol,
    create_structure_fn: Callable[[int], MetricsTree],
) -> None:
    logger = get_logger(LOGGER_NAME)
    db_metrics = await database_metrics.get_all_live_metrics()
    if not db_metrics:
        logger.debug("No persistent metrics found in database to rehydrate.")
        return
    async with lock:
        metrics_ref[0] = create_structure_fn(session_start_time_ms)
        rehydrated = rehydrate_metrics_from_records(db_metrics, metrics_ref[0])
    logger.debug("Successfully rehydrated %s/%s metrics.", rehydrated, len(db_metrics))
