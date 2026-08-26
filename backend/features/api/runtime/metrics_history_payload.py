"""SoAI - Metrics history payload normalization helpers [backend/features/api/runtime/metrics_history_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.types.json import is_json_value

if TYPE_CHECKING:
    from core.history.request.models import PreparedHistoryRequest
    from core.metrics.protocols import MetricsManagerProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "coerce_metrics_history_payload",
    "load_metrics_history_payload",
)


def coerce_metrics_history_payload(raw: JSONValue) -> JSONDict:
    if not isinstance(raw, dict):
        return {}
    output: JSONDict = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        if not is_json_value(value):
            continue
        output[key] = value
    return output


async def load_metrics_history_payload(
    metrics_manager: MetricsManagerProtocol,
    metric_key: str,
    history_request: PreparedHistoryRequest,
) -> JSONDict:
    raw = await metrics_manager.get_historical_data(
        metric_key,
        history_request.start_ts_ms,
        history_request.end_ts_ms,
        points=history_request.requested_points,
        interval_ms=history_request.resolution.interval_ms,
        aggregation=history_request.aggregation,
    )
    return coerce_metrics_history_payload(raw)
