"""SoAI - Metrics manager configuration constants and helpers [backend/metrics/manager/configuration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.task_groups import ManagedTaskGroup
from core.errors.exceptions import StateError
from core.history.config import build_metrics_history_config
from core.history.config_view import HistoryConfigView, build_history_config_view
from core.metrics.keyspace_base import (
    DIRECTOR_GAUGE_QUEUE_SIZE,
    DIRECTOR_REQUESTS_COMPLETED,
    DIRECTOR_REQUESTS_FAILED,
    DIRECTOR_REQUESTS_TOTAL,
    METRIC_BLOCK_BILLING,
    METRIC_KEY_TOTAL_TOKENS_GENERATED,
)
from core.types.json import is_json_value
from metrics.manager.internal_protocols import ManagedTaskGroupOwnerProtocol

if TYPE_CHECKING:
    from core.config.protocols import ConfigValue
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_history_config_from_raw",
    "build_metrics_history_view",
    "require_managed_task_group",
)

MAX_BILLING_CLIENT_CARDINALITY: int = 10000
MAX_BILLING_MODEL_CARDINALITY: int = 10000

CAPABILITIES_CACHE_TTL_SEC: float = 30.0


def _default_tracked_metrics() -> tuple[str, ...]:
    return (
        ".".join(DIRECTOR_REQUESTS_TOTAL),
        ".".join(DIRECTOR_REQUESTS_COMPLETED),
        ".".join(DIRECTOR_REQUESTS_FAILED),
        ".".join((METRIC_BLOCK_BILLING, METRIC_KEY_TOTAL_TOKENS_GENERATED)),
        ".".join(DIRECTOR_GAUGE_QUEUE_SIZE),
    )


def build_history_config_from_raw(raw_config: JSONValue | ConfigValue) -> tuple[JSONDict, bool]:
    if not is_json_value(raw_config):
        raise StateError("OBSERVABILITY.METRICS.METRICS_HISTORY must be JSON.")
    return build_metrics_history_config(
        raw_config,
        tracked_metrics_default=list(_default_tracked_metrics()),
    )


def build_metrics_history_view(
    history_config: JSONDict,
    history_enabled: bool,
    *,
    include_logging_interval_in_supported_intervals: bool = True,
    allow_empty_intervals: bool = False,
) -> HistoryConfigView:
    return build_history_config_view(
        history_config,
        enabled_default=history_enabled,
        logging_interval_default=3_000,
        max_points_default=50000,
        retention_hours_default=168,
        supported_intervals_default=(),
        supported_aggregations_default=(),
        include_logging_interval_in_supported_intervals=include_logging_interval_in_supported_intervals,
        allow_empty_intervals=allow_empty_intervals,
    )


def require_managed_task_group(lifecycle: ManagedTaskGroupOwnerProtocol) -> ManagedTaskGroup:
    managed_task_group = lifecycle.managed_task_group
    if managed_task_group is None:
        raise StateError("Metrics manager lifecycle did not initialize a managed task group.")
    return managed_task_group
