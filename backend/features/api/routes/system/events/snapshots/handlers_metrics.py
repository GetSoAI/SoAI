"""SoAI - Snapshot handlers for metrics resources [backend/features/api/routes/system/events/snapshots/handlers_metrics.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from core.errors.exceptions import ValidationError
from core.history.request.aggregation import normalize_history_aggregation_or_default
from core.history.request.export_window import parse_optional_export_time_window
from core.history.request.query import build_history_query
from core.metrics.export import (
    build_metrics_history_filename,
    iter_metrics_history_csv_bytes,
)
from core.system_api.route_paths import SOAI_METRICS_PREFIX
from features.api.routes.metrics.metrics_allowed_keys import METRICS_QUERY_ALLOWED_KEYS
from features.api.routes.system.events.snapshots.csv_export_preview import (
    collect_csv_preview_text,
)
from features.api.routes.system.events.snapshots.payload_validation import (
    require_supported_snapshot_payload_keys,
)
from features.api.runtime.metrics_history_payload import load_metrics_history_payload
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from fastapi import WebSocket

    from core.types.json import JSONDict, JSONValue

__all__ = (
    "snapshot_metrics_capabilities",
    "snapshot_metrics_export",
    "snapshot_metrics_history",
)


async def snapshot_metrics_capabilities(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    _ = data
    return await connection.api_context.dependencies.metrics_manager.get_capabilities()


async def snapshot_metrics_history(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    require_supported_snapshot_payload_keys(data, allowed_keys=set(METRICS_QUERY_ALLOWED_KEYS))
    metric_key_value = data.get("metric_key")
    metric_key = metric_key_value.strip() if isinstance(metric_key_value, str) else ""
    if not metric_key:
        raise ValidationError("system.metrics.history snapshot requires metric_key.")
    aggregation = normalize_history_aggregation_or_default(
        data.get("aggregation"),
        allowed_values={"avg", "min", "max", "count", "delta", "ohlc", "delta_ohlc"},
        default="avg",
    )
    metrics_mgr = connection.api_context.dependencies.metrics_manager
    history_request = build_history_query(
        {
            "start_ts_ms": data.get("start_ts_ms"),
            "end_ts_ms": data.get("end_ts_ms"),
            "points": data.get("points"),
            "interval_ms": data.get("interval_ms"),
            "aggregation": aggregation,
        },
        metrics_mgr.history_config,
        default_points=300,
        default_aggregation=aggregation,
        default_window_ms=3_600_000,
    )
    return await load_metrics_history_payload(metrics_mgr, metric_key, history_request)


async def snapshot_metrics_export(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    allowed_keys = {"start_ts_ms", "end_ts_ms"}
    require_supported_snapshot_payload_keys(data, allowed_keys=allowed_keys)
    start_ts_ms, end_ts_ms = parse_optional_export_time_window(data)
    filename = build_metrics_history_filename()
    csv_bytes = iter_metrics_history_csv_bytes(
        connection.api_context.dependencies.database_metrics,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
    )
    preview_text, preview_truncated = await collect_csv_preview_text(csv_bytes, max_bytes=256_000)
    query: dict[str, int] = {}
    if start_ts_ms is not None:
        query["start_ts_ms"] = start_ts_ms
    if end_ts_ms is not None:
        query["end_ts_ms"] = end_ts_ms
    base = f"{SOAI_METRICS_PREFIX}/export"
    download_url = f"{base}?{urlencode(query)}" if query else base
    return {
        "filename": filename,
        "download_url": download_url,
        "preview_text": preview_text,
        "preview_truncated": preview_truncated,
    }
