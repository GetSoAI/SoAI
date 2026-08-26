"""SoAI - PTY WebSocket event payload builders [backend/features/api/routes/system/events/websocket_pty_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.system_api.websocket_payloads import build_websocket_event_payload
from core.types.json import JSONDict
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes

__all__ = (
    "build_pty_busy_payload",
    "build_pty_connected_payload",
    "build_pty_disconnected_payload",
    "build_pty_exited_payload",
    "build_pty_output_payload",
)


def build_pty_output_payload(session_id: str, encoded_data: str) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.PTY_OUTPUT,
        {"session_id": session_id, "data": encoded_data},
    )


def build_pty_exited_payload(session_id: str, exit_code: int) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.PTY_EXITED,
        {"session_id": session_id, "exit_code": exit_code},
    )


def build_pty_busy_payload(session_id: str, busy: bool) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.PTY_BUSY,
        {"session_id": session_id, "busy": busy},
    )


def build_pty_connected_payload(result: JSONDict) -> JSONDict:
    return build_websocket_event_payload(WebSocketEventTypes.PTY_CONNECTED, result)


def build_pty_disconnected_payload(session_id: str) -> JSONDict:
    return build_websocket_event_payload(
        WebSocketEventTypes.PTY_DISCONNECTED,
        {"session_id": session_id},
    )
