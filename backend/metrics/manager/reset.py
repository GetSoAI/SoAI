"""SoAI - Metrics reset operations [backend/metrics/manager/reset.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.config.protocols import ConfigProtocol
from core.logging.trace import get_logger
from core.metrics.protocols import DatabaseMetricsProtocol
from metrics.manager.genesis import load_genesis_data
from metrics.manager.structure_factory import create_metrics_structure

if TYPE_CHECKING:
    from metrics.manager.types import MetricsTree

__all__ = ("reset_metrics_state",)

LOGGER_NAME = "SoAI.metrics.manager.reset"


async def reset_metrics_state(
    lock: asyncio.Lock,
    genesis_flush_lock: asyncio.Lock,
    genesis_requests_delta: list[int],
    genesis_tokens_delta: list[int],
    metrics_ref: list[MetricsTree],
    session_start_time_ms: int,
    config: ConfigProtocol,
    database_metrics: DatabaseMetricsProtocol,
) -> None:
    logger = get_logger(LOGGER_NAME)
    async with lock:
        await database_metrics.clear_all_live_metrics()
        metrics_ref[0] = create_metrics_structure(session_start_time_ms)
    if config.get_bool("OBSERVABILITY.METRICS.RESET_GENESIS_ON_CLEAR"):
        await database_metrics.reset_genesis_counters()
        async with genesis_flush_lock:
            genesis_requests_delta[0] = 0
            genesis_tokens_delta[0] = 0
    else:
        await load_genesis_data(lock, metrics_ref[0], database_metrics)
    logger.info("In-memory and persistent metrics have been reset.")
