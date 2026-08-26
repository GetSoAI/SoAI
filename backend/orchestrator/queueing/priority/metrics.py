"""SoAI - Model name sanitization for metrics collection [backend/orchestrator/queueing/priority/metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re

from core.metrics.keyspace_base import (
    DIRECTOR_GAUGE_QUEUE_SIZE,
    DIRECTOR_REQUESTS_BY_MODEL,
    DIRECTOR_REQUESTS_BY_VIRTUAL_MODEL,
    DIRECTOR_REQUESTS_QUEUED,
    DIRECTOR_REQUESTS_TOTAL,
)
from core.metrics.protocols import MetricsManagerProtocol
from core.tasks.orchestration_context import OrchestrationContext

__all__ = (
    "ModelMetricsRegistry",
    "record_priority_queue_enqueue_metrics",
    "sanitize_model_name_for_metrics",
)

MAX_MODEL_NAME_LENGTH_FOR_METRICS = 256
MODEL_NAME_SAFE_REGEX = r"^[\w\-.:/@]+$"
MAX_TRACKED_MODELS_FOR_METRICS = 500
OVERFLOW_MODEL_BUCKET = "other"
_SYNTHETIC_MODEL_BUCKETS: frozenset[str] = frozenset({"unknown", "invalid", OVERFLOW_MODEL_BUCKET})


def sanitize_model_name_for_metrics(model_name: str) -> str:
    if not model_name:
        return "unknown"
    if len(model_name) > MAX_MODEL_NAME_LENGTH_FOR_METRICS:
        return "invalid"
    if re.fullmatch(MODEL_NAME_SAFE_REGEX, model_name) is None:
        return "invalid"
    return model_name


class ModelMetricsRegistry:
    def __init__(self, max_tracked_models: int = MAX_TRACKED_MODELS_FOR_METRICS) -> None:
        self._tracked_models: set[str] = set()
        self._max_tracked_models = max_tracked_models

    def resolve_model_name(self, model_name: str) -> str:
        sanitized = sanitize_model_name_for_metrics(model_name)
        if sanitized in _SYNTHETIC_MODEL_BUCKETS:
            return sanitized
        if sanitized in self._tracked_models:
            return sanitized
        if len(self._tracked_models) >= self._max_tracked_models:
            return OVERFLOW_MODEL_BUCKET
        self._tracked_models.add(sanitized)
        return sanitized


def record_priority_queue_enqueue_metrics(
    metrics: MetricsManagerProtocol,
    registry: ModelMetricsRegistry,
    context: OrchestrationContext,
    backlog: int,
) -> None:
    metrics.increment_counter(*DIRECTOR_REQUESTS_TOTAL)
    metrics.increment_counter(*DIRECTOR_REQUESTS_QUEUED)
    execution_universal_id = (
        context.execution_universal_ids[0] if context.execution_universal_ids else None
    )
    if execution_universal_id:
        metrics.increment_counter(
            *DIRECTOR_REQUESTS_BY_MODEL,
            registry.resolve_model_name(execution_universal_id),
        )
    if context.virtual_model_name:
        metrics.increment_counter(
            *DIRECTOR_REQUESTS_BY_VIRTUAL_MODEL,
            registry.resolve_model_name(context.virtual_model_name),
        )
    metrics.set_gauge(*DIRECTOR_GAUGE_QUEUE_SIZE, value=backlog)
