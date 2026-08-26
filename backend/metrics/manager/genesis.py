"""SoAI - Genesis metrics operations [backend/metrics/manager/genesis.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.metrics.keyspace_base import (
    METRIC_BLOCK_GENESIS,
    METRIC_KEY_CURRENT_SESSION_MS,
    METRIC_KEY_FIRST_STARTUP_TS_MS,
    METRIC_KEY_REQUESTS_TOTAL,
    METRIC_KEY_TOKENS_TOTAL,
    METRIC_KEY_UPTIME_MS,
)
from core.metrics.protocols import DatabaseMetricsProtocol
from core.timing.monotonic import monotonic_ms
from core.validation.coercion import coerce_int_strict
from core.validation.integers import is_strict_int

if TYPE_CHECKING:
    from metrics.manager.types import MetricsTree

__all__ = (
    "augment_genesis_session_time",
    "flush_genesis_deltas",
    "load_genesis_data",
)


def augment_genesis_session_time(
    metrics: MetricsTree,
    session_start_time_monotonic_ms: int,
) -> None:
    session_ms = max(0, monotonic_ms() - int(session_start_time_monotonic_ms))
    if METRIC_BLOCK_GENESIS in metrics:
        genesis = metrics.get(METRIC_BLOCK_GENESIS)
        if not isinstance(genesis, dict):
            return
        genesis[METRIC_KEY_CURRENT_SESSION_MS] = session_ms
        uptime = genesis.get(METRIC_KEY_UPTIME_MS, 0)
        uptime_base = (
            int(uptime) if isinstance(uptime, int | float) and not isinstance(uptime, bool) else 0
        )
        genesis[METRIC_KEY_UPTIME_MS] = uptime_base + session_ms


async def load_genesis_data(
    lock: asyncio.Lock,
    metrics: MetricsTree,
    database_metrics: DatabaseMetricsProtocol,
) -> None:
    genesis_data = await database_metrics.get_genesis_data()
    async with lock:
        genesis = metrics.get(METRIC_BLOCK_GENESIS)
        if not isinstance(genesis, dict) or not isinstance(genesis_data, dict):
            return
        genesis[METRIC_KEY_UPTIME_MS] = coerce_int_strict(genesis_data.get(METRIC_KEY_UPTIME_MS))
        genesis[METRIC_KEY_REQUESTS_TOTAL] = coerce_int_strict(
            genesis_data.get(METRIC_KEY_REQUESTS_TOTAL),
        )
        genesis[METRIC_KEY_TOKENS_TOTAL] = coerce_int_strict(
            genesis_data.get(METRIC_KEY_TOKENS_TOTAL),
        )
        genesis[METRIC_KEY_FIRST_STARTUP_TS_MS] = coerce_int_strict(
            genesis_data.get(METRIC_KEY_FIRST_STARTUP_TS_MS),
        )


async def flush_genesis_deltas(
    lock: asyncio.Lock,
    metrics: MetricsTree,
    genesis_flush_lock: asyncio.Lock,
    genesis_requests_delta: list[int],
    genesis_tokens_delta: list[int],
    database_metrics: DatabaseMetricsProtocol,
) -> None:
    async with genesis_flush_lock:
        requests_delta = genesis_requests_delta[0]
        tokens_delta = genesis_tokens_delta[0]
        if requests_delta <= 0 and tokens_delta <= 0:
            return
        genesis_requests_delta[0] = 0
        genesis_tokens_delta[0] = 0
    await database_metrics.increment_genesis_counters(requests_delta, tokens_delta)
    async with lock:
        genesis = metrics.get(METRIC_BLOCK_GENESIS)
        if not isinstance(genesis, dict):
            return
        requests_total = genesis.get(METRIC_KEY_REQUESTS_TOTAL, 0)
        tokens_total = genesis.get(METRIC_KEY_TOKENS_TOTAL, 0)
        requests_base = int(requests_total) if is_strict_int(requests_total) else 0
        tokens_base = int(tokens_total) if is_strict_int(tokens_total) else 0
        genesis[METRIC_KEY_REQUESTS_TOTAL] = requests_base + requests_delta
        genesis[METRIC_KEY_TOKENS_TOTAL] = tokens_base + tokens_delta
