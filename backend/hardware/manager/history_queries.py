"""SoAI - Hardware historical data query and retrieval [backend/hardware/manager/history_queries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from core.config.clamped_numeric import read_config_nonnegative_int
from core.errors.exceptions import ValidationError
from core.hardware.protocols import DatabaseHardwareProtocol
from core.hardware.snapshot_lookup import resolve_component_device_id
from core.history.request.metadata import build_history_metadata_for_request
from core.history.request.preparation import (
    prepare_history_request_from_config,
)
from core.logging.protocols import TraceLogger
from hardware.manager.ohlc_post_processing import post_process_ohlc_data

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("get_historical_data",)
_HARDWARE_HISTORY_MAX_POINTS_DEFAULT = 50000


async def get_historical_data(
    *,
    logger: TraceLogger,
    history_enabled: bool,
    database_hardware: DatabaseHardwareProtocol | None,
    history_config: Mapping[str, JSONValue],
    monitoring_interval_ms: int,
    last_full_info: JSONDict,
    get_system_info: Callable[[list[str] | None, bool], Awaitable[JSONDict]],
    resolve_gpu_device_id: Callable[[int], str | None],
    component: str,
    start_ts_ms: int,
    end_ts_ms: int,
    points: int,
    gpu_index: int | None,
    identifier: str | None,
    interval_ms: int | None,
    aggregation: str,
) -> JSONDict:
    if not (history_enabled and database_hardware):
        logger.warning(
            "Attempted to get historical data, but history logging is disabled or database access is unavailable.",
        )
        return {}
    monitoring_interval_ms_int = int(monitoring_interval_ms)
    history_request = prepare_history_request_from_config(
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        points=points,
        interval_ms=interval_ms,
        aggregation=aggregation,
        history_config=history_config,
        max_points_default=_HARDWARE_HISTORY_MAX_POINTS_DEFAULT,
        logging_interval_default=monitoring_interval_ms_int,
        retention_hours_default=read_config_nonnegative_int(
            history_config,
            "DB_RETENTION_HOURS",
            0,
        ),
    )
    component_normalized = (component or "").strip().lower()
    expected_timestamps, resolved_interval_ms = (
        history_request.resolution.generate_timestamps_ms(),
        history_request.resolution.interval_ms,
    )
    resolved_identifier = identifier.strip() if isinstance(identifier, str) else None
    if component_normalized == "gpu":
        resolved_identifier = None
        if gpu_index is None:
            raise ValidationError("gpu_index is required for GPU historical data")
        resolved_identifier = resolve_gpu_device_id(gpu_index)
        if not resolved_identifier:
            raise ValidationError(f"Unknown gpu_index '{gpu_index}' for GPU historical data")
    elif resolved_identifier and component_normalized in {"cpu", "disk", "network"}:
        snapshot = last_full_info if isinstance(last_full_info, dict) else {}
        if not snapshot:
            snapshot = await get_system_info([component_normalized], True)
        resolved_identifier = resolve_component_device_id(
            component_normalized,
            resolved_identifier,
            snapshot,
        )
    history_data = await database_hardware.get_historical_hardware_data(
        component=component_normalized,
        start_ts_ms=history_request.resolution.start_ts_ms,
        end_ts_ms=history_request.resolution.end_ts_ms,
        interval_ms=resolved_interval_ms,
        aggregation=history_request.aggregation,
        max_points=history_request.resolution.bucket_count,
        identifier=resolved_identifier,
    )
    history_data["aggregation"], history_data["interval_ms"] = (
        history_request.aggregation,
        resolved_interval_ms,
    )
    metadata_value = history_data.get("metadata")
    metadata = metadata_value if isinstance(metadata_value, dict) else {}
    gap_count = 0
    raw_timestamps_value = history_data.get("timestamps_ms")
    timestamps_raw = raw_timestamps_value if isinstance(raw_timestamps_value, list) else []
    raw_timestamps: list[int] = []
    for timestamp in timestamps_raw:
        if isinstance(timestamp, bool):
            raw_timestamps.append(int(timestamp))
        elif isinstance(timestamp, int | float | str):
            try:
                raw_timestamps.append(int(timestamp))
            except (TypeError, ValueError):
                continue
    history_data["timestamps_ms"] = raw_timestamps
    if history_request.aggregation == "ohlc":
        history_data = post_process_ohlc_data(history_data, expected_timestamps)
        metadata_value = history_data.get("metadata")
        metadata = metadata_value if isinstance(metadata_value, dict) else {}
        gap_count_value = metadata.get("bucket_gap_count")
        if isinstance(gap_count_value, bool | int | float):
            gap_count = int(gap_count_value)
    timestamps_value = history_data.get("timestamps_ms")
    resolved_points = len(timestamps_value) if isinstance(timestamps_value, list) else 0
    metadata = build_history_metadata_for_request(
        history_request,
        supported_aggregations=_coerce_supported_aggregations(
            history_config.get("SUPPORTED_AGGREGATIONS"),
        ),
        gap_count=gap_count,
        resolved_points=resolved_points,
        base_metadata=metadata,
        extra_fields={
            "component": component_normalized,
            "device_id": resolved_identifier,
            "identifier": resolved_identifier,
            "monitoring_interval_ms": monitoring_interval_ms_int,
        },
    )
    history_data["metadata"] = metadata
    return history_data


def _coerce_supported_aggregations(value: JSONValue) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(item.strip())
    return result
