"""SoAI - Plugin-scoped metrics cleanup helpers [backend/metrics/manager/plugin_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.metrics.keyspace_base import (
    METRIC_BLOCK_BILLING,
    METRIC_BLOCK_DIRECTOR,
    METRIC_BLOCK_MODEL_MANAGER,
    METRIC_BLOCK_PLUGINS,
    METRIC_BLOCK_STATE,
    METRIC_BLOCK_USAGE,
    METRIC_KEY_DISCOVERIES_FAILED,
    METRIC_KEY_GAUGE_CONCURRENCY_ACTIVE,
    METRIC_KEY_GAUGE_CONCURRENCY_LIMIT,
    METRIC_KEY_GAUGE_CONCURRENCY_WAITERS,
    METRIC_KEY_GAUGE_HEALTH,
    METRIC_KEY_HEALTH_CHECK_RECOVERIES,
    METRIC_KEY_HEALTH_PING_FAILURES,
    METRIC_KEY_PERSISTENT_PLUGIN_REQUEST_TIMEOUTS,
    METRIC_KEY_PLUGIN_STATUS_CHANGES,
    METRIC_KEY_TOKENS_BY_MODEL,
    METRIC_KEY_TOKENS_BY_PLUGIN,
    METRIC_KEY_USAGE_BY_MODEL,
    METRIC_KEY_USAGE_BY_PLUGIN,
    METRIC_METRIC_GAUGES,
)
from core.state.state_names import PLUGIN_STATE_ABSENT

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from metrics.manager.types import MetricsTree, MetricValue

__all__ = (
    "collect_active_plugin_names",
    "prune_deleted_plugin_scoped_metrics",
    "purge_plugin_scoped_metrics",
)


def collect_active_plugin_names(plugin_records: list[JSONDict]) -> set[str]:
    active_plugins: set[str] = set()
    for record in plugin_records:
        raw_name = record.get("plugin_name")
        if not isinstance(raw_name, str):
            continue
        raw_state = record.get("state")
        state_name = raw_state.strip().upper() if isinstance(raw_state, str) else ""
        if state_name == PLUGIN_STATE_ABSENT:
            continue
        normalized_name = raw_name.strip().casefold()
        if normalized_name:
            active_plugins.add(normalized_name)
    return active_plugins


def _coerce_metric_map(value: MetricValue | None) -> dict[str, MetricValue] | None:
    if not isinstance(value, dict):
        return None
    return value


def _metric_key_matches_plugin(metric_key: str, plugin_name: str) -> bool:
    normalized_key = metric_key.strip().casefold()
    if not normalized_key:
        return False
    return normalized_key.startswith(f"{plugin_name}-") or normalized_key.startswith(
        f"{plugin_name}/",
    )


def _metric_key_matches_any_plugin(metric_key: str, plugin_names: set[str]) -> bool:
    for plugin_name in plugin_names:
        if _metric_key_matches_plugin(metric_key, plugin_name):
            return True
    return False


def _remove_plugin_entries_not_in_active_set(
    metric_map: dict[str, MetricValue] | None,
    active_plugins: set[str],
) -> int:
    if metric_map is None:
        return 0
    removed = 0
    for key in tuple(metric_map.keys()):
        if not isinstance(key, str):
            continue
        normalized_key = key.strip().casefold()
        if normalized_key in active_plugins:
            continue
        metric_map.pop(key, None)
        removed += 1
    return removed


def _remove_plugin_entries_matching_name(
    metric_map: dict[str, MetricValue] | None,
    plugin_name: str,
) -> int:
    if metric_map is None:
        return 0
    removed = 0
    for key in tuple(metric_map.keys()):
        if not isinstance(key, str):
            continue
        normalized_key = key.strip().casefold()
        if normalized_key != plugin_name:
            continue
        metric_map.pop(key, None)
        removed += 1
    return removed


def _remove_model_entries_not_in_active_set(
    metric_map: dict[str, MetricValue] | None,
    active_plugins: set[str],
) -> int:
    if metric_map is None:
        return 0
    removed = 0
    for key in tuple(metric_map.keys()):
        if not isinstance(key, str):
            continue
        if _metric_key_matches_any_plugin(key, active_plugins):
            continue
        metric_map.pop(key, None)
        removed += 1
    return removed


def _remove_model_entries_matching_plugin_prefix(
    metric_map: dict[str, MetricValue] | None,
    plugin_name: str,
) -> int:
    if metric_map is None:
        return 0
    removed = 0
    for key in tuple(metric_map.keys()):
        if not isinstance(key, str):
            continue
        if not _metric_key_matches_plugin(key, plugin_name):
            continue
        metric_map.pop(key, None)
        removed += 1
    return removed


def _plugin_scoped_metric_maps(
    metrics: MetricsTree,
) -> tuple[dict[str, MetricValue] | None, ...]:
    director_metrics = _coerce_metric_map(metrics.get(METRIC_BLOCK_DIRECTOR))
    director_gauges = (
        _coerce_metric_map(director_metrics.get(METRIC_METRIC_GAUGES))
        if director_metrics is not None
        else None
    )
    state_metrics = _coerce_metric_map(metrics.get(METRIC_BLOCK_STATE))
    model_manager_metrics = _coerce_metric_map(metrics.get(METRIC_BLOCK_MODEL_MANAGER))
    billing_metrics = _coerce_metric_map(metrics.get(METRIC_BLOCK_BILLING))
    usage_metrics = _coerce_metric_map(metrics.get(METRIC_BLOCK_USAGE))
    return (
        _coerce_metric_map(metrics.get(METRIC_BLOCK_PLUGINS)),
        (
            _coerce_metric_map(director_gauges.get(METRIC_KEY_GAUGE_HEALTH))
            if director_gauges is not None
            else None
        ),
        (
            _coerce_metric_map(director_gauges.get(METRIC_KEY_GAUGE_CONCURRENCY_LIMIT))
            if director_gauges is not None
            else None
        ),
        (
            _coerce_metric_map(director_gauges.get(METRIC_KEY_GAUGE_CONCURRENCY_ACTIVE))
            if director_gauges is not None
            else None
        ),
        (
            _coerce_metric_map(director_gauges.get(METRIC_KEY_GAUGE_CONCURRENCY_WAITERS))
            if director_gauges is not None
            else None
        ),
        (
            _coerce_metric_map(director_metrics.get(METRIC_KEY_HEALTH_CHECK_RECOVERIES))
            if director_metrics is not None
            else None
        ),
        (
            _coerce_metric_map(director_metrics.get(METRIC_KEY_HEALTH_PING_FAILURES))
            if director_metrics is not None
            else None
        ),
        (
            _coerce_metric_map(director_metrics.get(METRIC_KEY_PERSISTENT_PLUGIN_REQUEST_TIMEOUTS))
            if director_metrics is not None
            else None
        ),
        (
            _coerce_metric_map(state_metrics.get(METRIC_KEY_PLUGIN_STATUS_CHANGES))
            if state_metrics is not None
            else None
        ),
        (
            _coerce_metric_map(model_manager_metrics.get(METRIC_KEY_DISCOVERIES_FAILED))
            if model_manager_metrics is not None
            else None
        ),
        (
            _coerce_metric_map(billing_metrics.get(METRIC_KEY_TOKENS_BY_PLUGIN))
            if billing_metrics is not None
            else None
        ),
        (
            _coerce_metric_map(usage_metrics.get(METRIC_KEY_USAGE_BY_PLUGIN))
            if usage_metrics is not None
            else None
        ),
    )


def prune_deleted_plugin_scoped_metrics(metrics: MetricsTree, active_plugins: set[str]) -> int:
    removed = 0
    for metric_map in _plugin_scoped_metric_maps(metrics):
        removed += _remove_plugin_entries_not_in_active_set(metric_map, active_plugins)
    billing_metrics = _coerce_metric_map(metrics.get(METRIC_BLOCK_BILLING))
    if billing_metrics is not None:
        removed += _remove_model_entries_not_in_active_set(
            _coerce_metric_map(billing_metrics.get(METRIC_KEY_TOKENS_BY_MODEL)),
            active_plugins,
        )
    usage_metrics = _coerce_metric_map(metrics.get(METRIC_BLOCK_USAGE))
    if usage_metrics is not None:
        removed += _remove_model_entries_not_in_active_set(
            _coerce_metric_map(usage_metrics.get(METRIC_KEY_USAGE_BY_MODEL)),
            active_plugins,
        )
    return removed


def purge_plugin_scoped_metrics(metrics: MetricsTree, plugin_name: str) -> int:
    normalized_plugin_name = plugin_name.strip().casefold()
    if not normalized_plugin_name:
        return 0
    removed = 0
    for metric_map in _plugin_scoped_metric_maps(metrics):
        removed += _remove_plugin_entries_matching_name(metric_map, normalized_plugin_name)
    billing_metrics = _coerce_metric_map(metrics.get(METRIC_BLOCK_BILLING))
    if billing_metrics is not None:
        removed += _remove_model_entries_matching_plugin_prefix(
            _coerce_metric_map(billing_metrics.get(METRIC_KEY_TOKENS_BY_MODEL)),
            normalized_plugin_name,
        )
    usage_metrics = _coerce_metric_map(metrics.get(METRIC_BLOCK_USAGE))
    if usage_metrics is not None:
        removed += _remove_model_entries_matching_plugin_prefix(
            _coerce_metric_map(usage_metrics.get(METRIC_KEY_USAGE_BY_MODEL)),
            normalized_plugin_name,
        )
    return removed
