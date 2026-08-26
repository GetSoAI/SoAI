"""SoAI - Snapshot handlers for hardware history exports [backend/features/api/routes/system/events/snapshots/handlers_hardware_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from core.hardware.export import (
    build_hardware_history_filename,
    iter_hardware_history_csv_bytes,
)
from core.hardware.history_selection import (
    parse_optional_hardware_history_export_selection,
    parse_required_hardware_history_selection,
)
from core.history.request.export_window import parse_optional_export_time_window
from core.history.request.query import build_history_query
from core.system_api.route_paths import SOAI_HARDWARE_PREFIX
from features.api.routes.hardware.hardware_history_data_loading import (
    load_hardware_history_data,
)
from features.api.routes.system.events.snapshots.csv_export_preview import (
    collect_csv_preview_text,
)
from features.api.routes.system.events.snapshots.payload_validation import (
    require_supported_snapshot_payload_keys,
)
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from fastapi import WebSocket

    from core.types.json import JSONDict, JSONValue

__all__ = (
    "snapshot_hardware_export",
    "snapshot_hardware_history",
)


async def snapshot_hardware_history(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    allowed_keys = {
        "component",
        "gpu_index",
        "identifier",
        "start_ts_ms",
        "end_ts_ms",
        "points",
        "interval_ms",
        "aggregation",
    }
    require_supported_snapshot_payload_keys(data, allowed_keys=allowed_keys)
    selection = parse_required_hardware_history_selection(
        data,
        require_device_identifier=True,
        allow_cpu_identifier=True,
        reject_gpu_index_without_gpu=False,
        missing_component_message=(
            "hardware.history snapshot requires 'component' (cpu, gpu, disk, network)"
        ),
        invalid_component_message=(
            "Invalid component: {component}. Must be one of: cpu, gpu, disk, network"
        ),
    )
    api_context = connection.api_context
    history_config = api_context.dependencies.hw_manager.history_config
    history_request = build_history_query(
        {
            "start_ts_ms": data.get("start_ts_ms"),
            "end_ts_ms": data.get("end_ts_ms"),
            "points": data.get("points"),
            "interval_ms": data.get("interval_ms"),
            "aggregation": data.get("aggregation"),
        },
        history_config,
        default_points=300,
        default_aggregation="avg",
        default_window_ms=3_600_000,
    )
    return await load_hardware_history_data(
        hardware_manager=api_context.dependencies.hw_manager,
        history_request=history_request,
        component=selection.component or "",
        gpu_index=selection.gpu_index,
        identifier=selection.identifier,
    )


async def snapshot_hardware_export(
    data: JSONDict,
    connection: WebsocketConnection,
    _ws: WebSocket,
) -> JSONValue:
    allowed_keys = {"start_ts_ms", "end_ts_ms", "component", "identifier", "gpu_index"}
    require_supported_snapshot_payload_keys(data, allowed_keys=allowed_keys)
    start_ts_ms, end_ts_ms = parse_optional_export_time_window(data)
    selection = parse_optional_hardware_history_export_selection(data)
    filename = build_hardware_history_filename()
    csv_bytes = iter_hardware_history_csv_bytes(
        connection.api_context.dependencies.database_hardware,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        component=selection.component,
        identifier=selection.identifier,
        gpu_index=selection.gpu_index,
    )
    preview_text, preview_truncated = await collect_csv_preview_text(csv_bytes, max_bytes=256_000)
    query: dict[str, int | str] = {}
    if start_ts_ms is not None:
        query["start_ts_ms"] = start_ts_ms
    if end_ts_ms is not None:
        query["end_ts_ms"] = end_ts_ms
    if selection.component is not None:
        query["component"] = selection.component
    if selection.identifier is not None:
        query["identifier"] = selection.identifier
    if selection.gpu_index is not None:
        query["gpu_index"] = selection.gpu_index
    base = f"{SOAI_HARDWARE_PREFIX}/export"
    download_url = f"{base}?{urlencode(query)}" if query else base
    return {
        "filename": filename,
        "download_url": download_url,
        "preview_text": preview_text,
        "preview_truncated": preview_truncated,
    }
