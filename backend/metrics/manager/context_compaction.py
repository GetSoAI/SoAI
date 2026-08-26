"""SoAI - Metrics manager context compaction totals [backend/metrics/manager/context_compaction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.metrics.keyspace_base import (
    METRIC_BLOCK_USAGE,
    METRIC_KEY_COMPACTION_COMPLETED_COUNT,
    METRIC_KEY_COMPACTION_TOKENS_SAVED_TOTAL,
    METRIC_KEY_USAGE_COMPACTION,
)
from core.validation.integers import coerce_non_negative_exact_int_or_zero

if TYPE_CHECKING:
    from core.metrics.protocols import DatabaseMetricsProtocol
    from metrics.manager.types import MetricsTree, MetricValue

__all__ = ("refresh_context_compaction_usage_metrics",)


async def refresh_context_compaction_usage_metrics(
    lock: asyncio.Lock,
    metrics_ref: MetricsTree,
    database_metrics: DatabaseMetricsProtocol,
) -> None:
    totals = await database_metrics.get_context_compaction_metric_totals()
    completed_count = coerce_non_negative_exact_int_or_zero(totals.get("completed_count"))
    tokens_saved = coerce_non_negative_exact_int_or_zero(totals.get("tokens_saved"))
    async with lock:
        usage_value = metrics_ref.get(METRIC_BLOCK_USAGE)
        if not isinstance(usage_value, dict):
            return
        compaction_value = usage_value.get(METRIC_KEY_USAGE_COMPACTION)
        if not isinstance(compaction_value, dict):
            compaction_value = {}
            usage_value[METRIC_KEY_USAGE_COMPACTION] = compaction_value
        compaction_metrics: dict[str, MetricValue] = compaction_value
        compaction_metrics[METRIC_KEY_COMPACTION_COMPLETED_COUNT] = completed_count
        compaction_metrics[METRIC_KEY_COMPACTION_TOKENS_SAVED_TOTAL] = tokens_saved
