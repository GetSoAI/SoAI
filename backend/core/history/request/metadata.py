"""SoAI - History request metadata building [backend/core/history/request/metadata.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.history.request.models import HistoryRequestResolution, PreparedHistoryRequest

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_history_metadata",
    "build_history_metadata_for_request",
)


def build_history_metadata(
    *,
    base_metadata: Mapping[str, JSONValue] | None,
    extra_fields: Mapping[str, JSONValue] | None,
    resolution: HistoryRequestResolution,
    aggregation: str,
    requested_points: int,
    start_ts_ms: int,
    end_ts_ms: int,
    logging_interval_ms: int,
    supported_aggregations: Sequence[str],
    gap_count: int,
    resolved_points: int,
) -> JSONDict:
    metadata: JSONDict = {}
    if base_metadata:
        metadata.update(dict(base_metadata))
    if extra_fields:
        metadata.update(dict(extra_fields))
    supported_lower = {
        str(value).strip().lower()
        for value in supported_aggregations
        if isinstance(value, str) and value.strip()
    }
    requested_duration_ms = end_ts_ms - start_ts_ms
    metadata.update(
        {
            "interval_ms": resolution.interval_ms,
            "requested_interval_ms": resolution.requested_interval_ms,
            "interval_source": resolution.interval_source,
            "aggregation": aggregation,
            "start_ts_ms": resolution.start_ts_ms,
            "requested_start_ts_ms": start_ts_ms,
            "end_ts_ms": end_ts_ms,
            "requested_end_ts_ms": end_ts_ms,
            "aligned_start_ts_ms": resolution.aligned_start_ts_ms,
            "aligned_end_ts_ms": resolution.aligned_end_ts_ms,
            "duration_ms": resolution.duration_ms,
            "requested_duration_ms": requested_duration_ms,
            "points": resolved_points,
            "requested_points": requested_points,
            "effective_points": resolved_points,
            "max_points": resolution.max_points,
            "bucket_count": resolution.bucket_count,
            "bucket_gap_count": gap_count,
            "logging_interval_ms": logging_interval_ms,
            "supports_ohlc": "ohlc" in supported_lower,
            "retention_applied": resolution.retention_applied,
            "retention_start_ts_ms": resolution.retention_start_ts_ms,
            "supported_intervals_ms": list(resolution.supported_intervals_ms),
        },
    )
    return metadata


def build_history_metadata_for_request(
    history_request: PreparedHistoryRequest,
    *,
    supported_aggregations: Sequence[str],
    gap_count: int,
    resolved_points: int,
    base_metadata: Mapping[str, JSONValue] | None = None,
    extra_fields: Mapping[str, JSONValue] | None = None,
) -> JSONDict:
    return build_history_metadata(
        base_metadata=base_metadata,
        extra_fields=extra_fields,
        resolution=history_request.resolution,
        aggregation=history_request.aggregation,
        requested_points=history_request.requested_points,
        start_ts_ms=history_request.start_ts_ms,
        end_ts_ms=history_request.end_ts_ms,
        logging_interval_ms=history_request.logging_interval_ms,
        supported_aggregations=supported_aggregations,
        gap_count=gap_count,
        resolved_points=resolved_points,
    )
