"""SoAI - Snapshot WebSocket payload builders [backend/features/api/routes/system/events/snapshots/payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.system_api.websocket_payloads import build_websocket_event_payload
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict, JSONValue
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes

__all__ = (
    "build_snapshot_error_event",
    "build_snapshot_response_event",
)


def build_snapshot_response_event(resource: str, snapshot_id: str, data: JSONValue) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.SNAPSHOT_RESPONSE,
        {
            "resource": resource,
            "snapshot_id": snapshot_id,
            "data": data,
            "timestamp_ms": int(epoch_ms()),
        },
    )


def build_snapshot_error_event(
    resource: str,
    snapshot_id: str,
    message: str | None,
    error: JSONValue,
) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.SNAPSHOT_ERROR,
        {
            "resource": resource,
            "snapshot_id": snapshot_id,
            "message": message,
            "error": error,
            "timestamp_ms": int(epoch_ms()),
        },
    )
