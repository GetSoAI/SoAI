"""SoAI - Metrics reset operations [backend/metrics/manager/reset.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from core.metrics.protocols import DatabaseMetricsProtocol
from metrics.manager.genesis import load_genesis_data
from metrics.manager.structure_factory import create_metrics_structure

if TYPE_CHECKING:
    from metrics.manager.types import MetricsTree

__all__ = (
    "reset_metrics_state",
    "serialize_with_metrics_reset",
)

LOGGER_NAME = "SoAI.metrics.manager.reset"


def serialize_with_metrics_reset(
    reset_lock: asyncio.Lock,
    task: Callable[[], Awaitable[None]],
) -> Callable[[], Awaitable[None]]:
    async def run_serialized() -> None:
        async with reset_lock:
            await task()

    return run_serialized


async def reset_metrics_state(
    lock: asyncio.Lock,
    genesis_flush_lock: asyncio.Lock,
    genesis_requests_delta: list[int],
    genesis_tokens_delta: list[int],
    metrics_ref: list[MetricsTree],
    session_start_time_ms: int,
    reset_genesis_counters: bool,
    database_metrics: DatabaseMetricsProtocol,
) -> int:
    metrics = create_metrics_structure(session_start_time_ms)
    if not reset_genesis_counters:
        await load_genesis_data(lock, metrics, database_metrics)
    async with genesis_flush_lock:
        async with lock:
            cleared_through_ms = await database_metrics.reset_metrics_storage(
                reset_genesis_counters
            )
            if reset_genesis_counters:
                genesis_requests_delta[0] = 0
                genesis_tokens_delta[0] = 0
            metrics_ref[0] = metrics
    get_logger(LOGGER_NAME).info("In-memory metrics, live persistence, and history were reset.")
    return cleared_through_ms
