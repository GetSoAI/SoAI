"""SoAI - MCP worker non-critical metrics reporting [backend/mcp/worker/metrics_reporting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.metrics.protocols import MetricsRecorderProtocol
from core.types.json import JSONValue

__all__ = (
    "record_worker_metric_counter",
    "record_worker_metric_gauge",
    "record_worker_metric_timing",
)


def record_worker_metric_counter(
    metrics: MetricsRecorderProtocol,
    logger: LoggerProtocol,
    keys: tuple[str, ...],
    *,
    operation: str,
    details: Mapping[str, JSONValue],
    value: int = 1,
) -> None:
    try:
        metrics.increment_counter(*keys, value=value)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            coerced,
            message="Failed to increment RAG worker metric.",
            operation=operation,
            details=details,
            level="debug",
        )


def record_worker_metric_gauge(
    metrics: MetricsRecorderProtocol,
    logger: LoggerProtocol,
    keys: tuple[str, ...],
    *,
    operation: str,
    details: Mapping[str, JSONValue],
    value: float,
) -> None:
    try:
        metrics.set_gauge(*keys, value=value)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            coerced,
            message="Failed to update RAG worker metric.",
            operation=operation,
            details=details,
            level="debug",
        )


def record_worker_metric_timing(
    metrics: MetricsRecorderProtocol,
    logger: LoggerProtocol,
    keys: tuple[str, ...],
    *,
    operation: str,
    details: Mapping[str, JSONValue],
    duration_ms: float,
) -> None:
    try:
        metrics.record_timing(*keys, duration_ms=duration_ms)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_handled_exception(
            logger,
            coerced,
            message="Failed to record RAG worker metric.",
            operation=operation,
            details=details,
            level="debug",
        )
