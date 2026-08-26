"""SoAI - Outcome finalization metric emission [backend/orchestrator/execution/outcome_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.logging.trace import get_logger
from core.metrics.keyspace_base import (
    DIRECTOR_GAUGE_REQUEST_LATENCY_MS,
    DIRECTOR_REQUESTS,
    DIRECTOR_REQUESTS_CANCELLED,
    DIRECTOR_REQUESTS_COMPLETED,
    DIRECTOR_REQUESTS_FAILED,
    METRIC_KEY_CANCELLED,
    METRIC_KEY_COMPLETED,
    METRIC_KEY_FAILED,
)
from core.metrics.protocols import MetricsManagerProtocol

if TYPE_CHECKING:
    from core.tasks.task import Task

__all__ = (
    "increment_outcome_counter_noncritical",
    "increment_outcome_metrics",
)

LOGGER_NAME = "SoAI.orchestrator.execution.outcome_metrics"
OPERATION = "orchestrator.execution.outcome_metrics.increment_outcome_counter_noncritical"


def increment_outcome_counter_noncritical(
    metrics: MetricsManagerProtocol,
    counter_path: tuple[str, ...],
    *,
    task_id: str,
) -> None:
    try:
        metrics.increment_counter(*counter_path)
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(exception, operation=OPERATION)
        log_exception(
            get_logger(LOGGER_NAME),
            coerced,
            message="Terminal outcome metric emission failed.",
            operation=OPERATION,
            details={"task_id": task_id, "counter_path": ".".join(counter_path)},
            level="warning",
        )


def _get_director_request_latency_key() -> str:
    return ".".join(DIRECTOR_GAUGE_REQUEST_LATENCY_MS)


def increment_outcome_metrics(
    metrics: MetricsManagerProtocol,
    metrics_counter: str | None,
    task: Task,
) -> None:
    if not metrics_counter:
        return
    if metrics_counter == METRIC_KEY_COMPLETED:
        metrics.increment_counter(*DIRECTOR_REQUESTS_COMPLETED)
        metrics.increment_genesis_request()
        record_completed_request_latency(metrics, task)
        return
    if metrics_counter == METRIC_KEY_CANCELLED:
        metrics.increment_counter(*DIRECTOR_REQUESTS_CANCELLED)
        return
    if metrics_counter == METRIC_KEY_FAILED:
        metrics.increment_counter(*DIRECTOR_REQUESTS_FAILED)
        return
    metrics.increment_counter(*DIRECTOR_REQUESTS, metrics_counter)


def record_completed_request_latency(metrics: MetricsManagerProtocol, task: Task) -> None:
    completed_at_ms = task.completed_at_ms
    if completed_at_ms is None:
        return
    duration_ms = int(completed_at_ms) - int(task.created_at_ms)
    if duration_ms <= 0:
        return
    metrics.set_gauge(*DIRECTOR_GAUGE_REQUEST_LATENCY_MS, value=duration_ms)
    metrics.record_historical_metric(
        _get_director_request_latency_key(),
        duration_ms,
        observed_at_ms=completed_at_ms,
    )
