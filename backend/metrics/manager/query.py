"""SoAI - Metrics query and aggregation functions [backend/metrics/manager/query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError
from core.logging.trace import get_logger
from core.serialization.json import normalize_for_json
from core.timing.monotonic import monotonic_ms
from metrics.manager.capabilities import build_capabilities_response
from metrics.manager.genesis import augment_genesis_session_time
from metrics.manager.internal_protocols import TokenRateCalculatorProtocol
from metrics.manager.pruning import calculate_stats_recursive

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from metrics.manager.types import MetricsTree, MetricValue

__all__ = (
    "aggregate_all_metrics",
    "get_capabilities_snapshot",
    "metric_value_from_json",
    "should_refresh_capabilities_cache",
    "snapshot_metrics_locked",
)

LOGGER_NAME = "SoAI.metrics.manager.query"
OPERATION = "metrics_manager.aggregate_all_metrics"


def _recursive_copy_metrics(source: Mapping[str, MetricValue]) -> dict[str, MetricValue]:
    result: dict[str, MetricValue] = {}
    for key, value in source.items():
        if isinstance(value, dict):
            result[key] = _recursive_copy_metrics(value)
        else:
            result[key] = value
    return result


def metric_value_from_json(value: JSONValue) -> MetricValue | None:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list):
        converted: list[MetricValue] = []
        for entry in value:
            converted_value = metric_value_from_json(entry)
            if converted_value is None:
                return None
            converted.append(converted_value)
        return converted
    if isinstance(value, dict):
        converted_dict: dict[str, MetricValue] = {}
        for key, entry in value.items():
            if not isinstance(key, str):
                return None
            converted_value = metric_value_from_json(entry)
            if converted_value is None:
                return None
            converted_dict[key] = converted_value
        return converted_dict
    return None


async def snapshot_metrics_locked(
    lock: asyncio.Lock,
    metrics_ref: MetricsTree,
) -> MetricsTree:
    async with lock:
        return _recursive_copy_metrics(metrics_ref)


def should_refresh_capabilities_cache(
    cache: JSONDict | None,
    cache_timestamp: float,
    ttl_sec: float,
) -> bool:
    if cache is None:
        return True
    now = time.monotonic()
    return (now - cache_timestamp) >= ttl_sec


async def get_capabilities_snapshot(
    lock: asyncio.Lock,
    metrics_ref: MetricsTree,
    history_config: JSONDict,
    history_enabled: bool,
) -> JSONDict:
    async with lock:
        return build_capabilities_response(metrics_ref, history_config, history_enabled)


async def aggregate_all_metrics(
    snapshot_fn: Callable[[], Awaitable[MetricsTree]],
    token_rate_calculator: TokenRateCalculatorProtocol,
    get_capabilities_fn: Callable[[], Awaitable[JSONDict]],
    session_start_time_monotonic_ms: int,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    metrics_copy = await snapshot_fn()
    token_rates = token_rate_calculator.get_rates(monotonic_ms())
    converted_token_rates = metric_value_from_json(token_rates)
    if converted_token_rates is not None:
        metrics_copy["token_rates"] = converted_token_rates
    calculate_stats_recursive(metrics_copy)
    capabilities = await get_capabilities_fn()
    converted_capabilities = metric_value_from_json(capabilities)
    if converted_capabilities is not None:
        metrics_copy["capabilities"] = converted_capabilities
    augment_genesis_session_time(metrics_copy, session_start_time_monotonic_ms)
    try:
        normalized = normalize_for_json(metrics_copy)
        if not isinstance(normalized, dict):
            raise ProcessError("Metrics payload serialization failed.")
        return normalized
    except (TypeError, ValueError) as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="metrics_manager.aggregate_all_metrics",
        )
        log_exception(
            logger,
            coerced,
            message="Failed to serialize metrics",
            operation=OPERATION,
        )
        raise ProcessError(
            "Metrics payload serialization failed.",
            details={"reason": str(exception)},
        ) from exception
