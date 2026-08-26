"""SoAI - Metrics snapshot, capability, and history queries [backend/metrics/manager/query_surface.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from metrics.manager.configuration import CAPABILITIES_CACHE_TTL_SEC
from metrics.manager.history import get_historical_data
from metrics.manager.internal_protocols import (
    MetricsQuerySurfaceProtocol,
    TokenRateCalculatorProtocol,
)
from metrics.manager.query import (
    aggregate_all_metrics,
    get_capabilities_snapshot,
    should_refresh_capabilities_cache,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from metrics.manager.types import MetricsTree

__all__ = (
    "MetricsHistoryMethodRequest",
    "get_all_metrics",
    "get_all_metrics_method",
    "get_capabilities",
    "get_capabilities_method",
    "get_historical_data_method",
)


@dataclass(frozen=True, slots=True)
class MetricsHistoryMethodRequest:
    metric_key: str
    start_ts_ms: int
    end_ts_ms: int
    points: int
    interval_ms: int | None
    aggregation: str


async def get_capabilities(
    *,
    lock: asyncio.Lock,
    metrics_ref: list[MetricsTree],
    history_config: JSONDict,
    history_enabled: bool,
    capabilities_cache: JSONDict | None,
    capabilities_cache_timestamp: float,
) -> tuple[JSONDict, float]:
    if not should_refresh_capabilities_cache(
        capabilities_cache,
        capabilities_cache_timestamp,
        CAPABILITIES_CACHE_TTL_SEC,
    ):
        cached_capabilities = capabilities_cache
        if cached_capabilities is not None:
            return (cached_capabilities, capabilities_cache_timestamp)
    caps = await get_capabilities_snapshot(
        lock,
        metrics_ref[0],
        history_config,
        history_enabled,
    )
    return (caps, time.monotonic())


async def get_capabilities_method(self: MetricsQuerySurfaceProtocol) -> JSONDict:
    capabilities, timestamp = await get_capabilities(
        lock=self.lock,
        metrics_ref=self.metrics_ref,
        history_config=self.history_config,
        history_enabled=self.history_enabled,
        capabilities_cache=self.capabilities_cache,
        capabilities_cache_timestamp=self.capabilities_cache_timestamp,
    )
    self.capabilities_cache = capabilities
    self.capabilities_cache_timestamp = timestamp
    return capabilities


async def get_all_metrics(
    *,
    snapshot_metrics: Callable[[], Awaitable[MetricsTree]],
    token_rate_calculator: TokenRateCalculatorProtocol,
    get_capabilities_callable: Callable[[], Awaitable[JSONDict]],
    session_start_time_monotonic_ms: int,
) -> JSONDict:
    return await aggregate_all_metrics(
        snapshot_metrics,
        token_rate_calculator,
        get_capabilities_callable,
        session_start_time_monotonic_ms,
    )


async def get_all_metrics_method(self: MetricsQuerySurfaceProtocol) -> JSONDict:
    return await get_all_metrics(
        snapshot_metrics=self.snapshot_metrics,
        token_rate_calculator=self.token_rate_calculator,
        get_capabilities_callable=self.get_capabilities,
        session_start_time_monotonic_ms=self.session_start_time_monotonic_ms,
    )


async def get_historical_data_method(
    self: MetricsQuerySurfaceProtocol,
    request: MetricsHistoryMethodRequest,
) -> JSONDict:
    return await get_historical_data(
        request.metric_key,
        request.start_ts_ms,
        request.end_ts_ms,
        request.points,
        request.interval_ms,
        request.aggregation,
        self.history_config,
        self.history_enabled,
        self.database_metrics,
    )
