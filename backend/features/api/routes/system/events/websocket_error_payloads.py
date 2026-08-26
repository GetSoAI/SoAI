"""SoAI - WebSocket error event payload builders [backend/features/api/routes/system/events/websocket_error_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.error_types import ErrorType
from core.system_api.websocket_payloads import build_websocket_error_payload
from core.system_api.websocket_run_events import build_websocket_run_error_event
from core.types.json import JSONDict
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes

__all__ = (
    "build_run_error_event",
    "build_websocket_error_event",
    "resolve_websocket_error_type_for_soai_code",
)


def resolve_websocket_error_type_for_soai_code(error_code: str) -> str:
    if error_code == ErrorType.INVALID_REQUEST.value:
        return WebSocketEventTypes.INVALID_REQUEST
    if error_code in {ErrorType.AUTHENTICATION_ERROR.value, ErrorType.FORBIDDEN.value}:
        return WebSocketEventTypes.FORBIDDEN
    if error_code == ErrorType.NOT_FOUND.value:
        return WebSocketEventTypes.NOT_FOUND
    if error_code == ErrorType.CONFLICT.value:
        return WebSocketEventTypes.CONFLICT
    return WebSocketEventTypes.SERVER_ERROR


def build_websocket_error_event(
    *,
    trace_id: str | None,
    error_type: str,
    message: str,
    code: str,
    task_id: str | None = None,
    details: JSONDict | None = None,
    run_id: str | None = None,
) -> JSONDict:
    extra: JSONDict = {}
    if task_id:
        extra["task_id"] = task_id
    if run_id:
        extra["run_id"] = run_id
    return build_websocket_error_payload(
        trace_id=trace_id,
        event_type=error_type,
        message=message,
        code=code,
        details=details,
        extra=extra,
    )


def build_run_error_event(
    *,
    event_type: str,
    run_id: str,
    message: str,
    code: str,
    task_id: str | None = None,
) -> JSONDict:
    return build_websocket_run_error_event(
        event_type=event_type,
        run_id=run_id,
        message=message,
        code=code,
        task_id=task_id,
    )
