"""SoAI - Historical metrics logging and query operations [backend/metrics/manager/history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ServiceUnavailableError, ValidationError
from core.history.request.metadata import build_history_metadata_for_request
from core.history.request.preparation import (
    HistoryRequestDefaults,
    prepare_history_request_with_defaults,
)
from core.logging.trace import get_logger
from core.metrics.protocols import DatabaseMetricsProtocol
from core.validation.coercion import coerce_json_dict_stringify_non_json_values
from core.validation.numberish import require_int_from_numberish
from core.validation.strings import coerce_trimmed_nonempty_str_list
from metrics.manager.aggregation import extract_tracked_metrics
from metrics.manager.configuration import build_metrics_history_view
from metrics.manager.history_payloads import (
    process_ohlc_history,
    process_standard_history,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from metrics.manager.types import MetricsTree

__all__ = (
    "get_historical_data",
    "log_historical_metrics",
    "prune_historical_metrics",
)

LOGGER_NAME = "SoAI.metrics.manager.history"


async def log_historical_metrics(
    metrics: MetricsTree,
    history_config: JSONDict,
    database_metrics: DatabaseMetricsProtocol,
) -> None:
    keys_to_track = coerce_trimmed_nonempty_str_list(history_config.get("TRACKED_METRICS", []))
    if not keys_to_track:
        return
    snapshot_to_log = extract_tracked_metrics(metrics, keys_to_track)
    if snapshot_to_log:
        await database_metrics.log_historical_metrics(snapshot_to_log)


async def prune_historical_metrics(
    history_config: JSONDict,
    database_metrics: DatabaseMetricsProtocol,
) -> None:
    retention_hours = require_int_from_numberish(
        history_config.get("DB_RETENTION_HOURS", 168),
        field="DB_RETENTION_HOURS",
        bool_message="DB_RETENTION_HOURS must be a non-negative integer.",
        invalid_message="DB_RETENTION_HOURS must be a non-negative integer.",
    )
    if retention_hours < 0:
        raise ValidationError("DB_RETENTION_HOURS must be a non-negative integer.")
    await database_metrics.prune_old_historical_metrics(retention_hours)


async def get_historical_data(
    metric_key: str,
    start_ts_ms: int,
    end_ts_ms: int,
    points: int,
    interval_ms: int | None,
    aggregation: str,
    history_config: JSONDict,
    history_enabled: bool,
    database_metrics: DatabaseMetricsProtocol,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    if not history_enabled or database_metrics is None:
        message = "Historical metrics are disabled or database metrics are unavailable."
        logger.warning(message)
        raise ServiceUnavailableError(message)
    if not metric_key:
        raise ValidationError("metric_key must be a non-empty string")
    metric_key = metric_key.strip()
    if not metric_key:
        raise ValidationError("metric_key must be a non-empty string")
    history_view = build_metrics_history_view(history_config, history_enabled)
    supported_aggregations = list(history_view.supported_aggregations)
    history_request = prepare_history_request_with_defaults(
        defaults=HistoryRequestDefaults(
            max_points_default=50000,
            logging_interval_default=3_000,
            retention_hours_default=168,
        ),
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        points=points,
        interval_ms=interval_ms,
        aggregation=aggregation,
        history_config=history_config,
    )
    resolved_interval_ms = history_request.resolution.interval_ms
    expected_timestamps = history_request.resolution.generate_timestamps_ms()
    history_resolution = history_request.resolution
    history_data = await database_metrics.get_historical_metrics_data_aggregated(
        metric_key=metric_key,
        start_ts_ms=history_resolution.start_ts_ms,
        end_ts_ms=history_resolution.end_ts_ms,
        interval_ms=resolved_interval_ms,
        aggregation=history_request.aggregation,
        max_points=history_resolution.bucket_count,
    )
    history_data["aggregation"] = history_request.aggregation
    history_data["interval_ms"] = resolved_interval_ms
    metadata = coerce_json_dict_stringify_non_json_values(history_data.get("metadata"))
    if history_request.aggregation in ("ohlc", "delta_ohlc"):
        gap_count = process_ohlc_history(history_data, expected_timestamps, metric_key)
    else:
        gap_count = process_standard_history(
            history_data,
            expected_timestamps,
            metric_key,
            history_request.aggregation,
        )
    timestamps_value = history_data.get("timestamps_ms")
    resolved_points = len(timestamps_value) if isinstance(timestamps_value, list | tuple) else 0
    metadata = build_history_metadata_for_request(
        history_request,
        supported_aggregations=supported_aggregations,
        gap_count=gap_count,
        resolved_points=resolved_points,
        base_metadata=metadata,
        extra_fields={"metric_key": metric_key},
    )
    history_data["metadata"] = metadata
    return history_data
