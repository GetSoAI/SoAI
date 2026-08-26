"""SoAI - Log stream WebSocket event payload builders [backend/features/api/routes/system/events/websocket_log_stream/events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.system_api.websocket_payloads import build_websocket_event_payload
from core.types.json import JSONDict
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes

__all__ = (
    "build_log_batch_payload",
    "build_log_stream_closed_payload",
    "build_log_stream_reconfigured_payload",
    "build_log_stream_subscribed_payload",
    "build_log_stream_unsubscribed_payload",
)


def build_log_batch_payload(source_name: str, mode: str, entries: list[JSONDict]) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.LOG_BATCH,
        {"source_name": source_name, "mode": mode, "entries": entries},
    )


def build_log_stream_reconfigured_payload(source_name: str) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.LOG_STREAM_RECONFIGURED,
        {"source_name": source_name},
    )


def build_log_stream_closed_payload(source_name: str) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.LOG_STREAM_CLOSED,
        {"source_name": source_name},
    )


def build_log_stream_subscribed_payload(source_name: str) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.LOG_STREAM_SUBSCRIBED,
        {"source_name": source_name},
    )


def build_log_stream_unsubscribed_payload(source_name: str) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.LOG_STREAM_UNSUBSCRIBED,
        {"source_name": source_name},
    )
