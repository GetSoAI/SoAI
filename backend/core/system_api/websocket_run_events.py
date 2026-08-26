"""SoAI - WebSocket run event payload builders [backend/core/system_api/websocket_run_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.system_api.websocket_payloads import (
    build_websocket_error_payload,
    build_websocket_event_payload,
)
from core.types.json import JSONDict

__all__ = (
    "build_websocket_run_error_event",
    "build_websocket_run_event",
)


def build_websocket_run_event(
    *,
    event_type: str,
    run_id: str,
    task_id: str | None = None,
    fields: JSONDict | None = None,
) -> JSONDict:
    fields_payload: JSONDict = dict(fields or {})
    fields_payload["run_id"] = run_id
    if task_id is not None and task_id.strip():
        fields_payload["task_id"] = task_id.strip()
    return build_websocket_event_payload(event_type, fields_payload)


def build_websocket_run_error_event(
    *,
    event_type: str,
    run_id: str,
    message: str,
    code: str,
    task_id: str | None = None,
) -> JSONDict:
    fields: JSONDict = {"run_id": run_id, "code": code}
    if task_id is not None and task_id.strip():
        fields["task_id"] = task_id.strip()
    return build_websocket_error_payload(
        event_type=event_type,
        trace_id=None,
        message=message,
        code=code,
        extra=fields,
    )
