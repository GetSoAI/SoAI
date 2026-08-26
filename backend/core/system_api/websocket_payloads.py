"""SoAI - WebSocket payload envelope builders [backend/core/system_api/websocket_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.public_projection import project_public_error_code
from core.types.json import JSONDict

__all__ = (
    "build_websocket_error_payload",
    "build_websocket_event_payload",
)


def build_websocket_event_payload(event_type: str, fields: JSONDict | None = None) -> JSONDict:
    payload: JSONDict = dict(fields or {})
    payload["type"] = event_type
    return payload


def build_websocket_error_payload(
    *,
    trace_id: str | None,
    event_type: str,
    message: str,
    code: str,
    details: JSONDict | None = None,
    extra: JSONDict | None = None,
) -> JSONDict:
    error_payload = project_public_error_code(
        code=code,
        message=message,
        details=details,
        trace_id=trace_id,
    )
    error_fields = error_payload.to_dict()
    fields: JSONDict = dict(extra or {})
    fields["message"] = error_fields.get("message")
    fields["error"] = error_fields
    return build_websocket_event_payload(event_type, fields)
