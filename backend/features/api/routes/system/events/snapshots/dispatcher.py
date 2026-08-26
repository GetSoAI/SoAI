"""SoAI - WebSocket snapshot request dispatcher [backend/features/api/routes/system/events/snapshots/dispatcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic
from fastapi import WebSocket

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.state.access import AccessAction
from features.api.routes.system.events.internal_protocols import WebSocketMessageTypes
from features.api.routes.system.events.permissions import SNAPSHOT_PERMISSION_RULES
from features.api.routes.system.events.snapshots.error_events import (
    send_permission_error,
    send_snapshot_error_event,
)
from features.api.routes.system.events.snapshots.payloads import (
    build_snapshot_response_event,
)
from features.api.routes.system.events.snapshots.resource_registry import (
    resolve_snapshot_handler,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.streaming.websocket import WebsocketConnection

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )

__all__ = ("handle_snapshot_request",)

LOGGER_NAME = "SoAI.features.api.dispatcher"
OPERATION = "api_system.websocket.system_events.snapshots.request"
_SNAPSHOT_REQUIRED_ENVELOPE_KEYS: frozenset[str] = frozenset(
    {"type", "resource", "snapshot_id", "tab_id", "protocol_version", "payload"},
)


def _parse_snapshot_request_envelope(data: JSONDict) -> tuple[str, str, JSONDict]:
    for required_key in _SNAPSHOT_REQUIRED_ENVELOPE_KEYS:
        if required_key not in data:
            raise ValidationError(f"Snapshot request envelope missing field: {required_key}")
    for envelope_key in data:
        if isinstance(envelope_key, str) and envelope_key not in _SNAPSHOT_REQUIRED_ENVELOPE_KEYS:
            raise ValidationError("Snapshot request envelope contains unsupported fields.")
    message_type_value = data.get("type")
    message_type = message_type_value if isinstance(message_type_value, str) else ""
    if message_type != WebSocketMessageTypes.REQUEST_SNAPSHOT:
        raise ValidationError("Invalid snapshot request envelope type.")
    resource_value = data.get("resource")
    resource = resource_value.strip() if isinstance(resource_value, str) else ""
    if not resource:
        raise ValidationError("Snapshot request envelope field 'resource' is invalid.")
    snapshot_id_value = data.get("snapshot_id")
    snapshot_id = snapshot_id_value.strip() if isinstance(snapshot_id_value, str) else ""
    if not snapshot_id:
        raise ValidationError("Snapshot request envelope field 'snapshot_id' is invalid.")
    tab_id_value = data.get("tab_id")
    tab_id = tab_id_value.strip() if isinstance(tab_id_value, str) else ""
    if not tab_id:
        raise ValidationError("Snapshot request envelope field 'tab_id' is invalid.")
    payload_value = data.get("payload")
    if not isinstance(payload_value, dict):
        raise ValidationError("Snapshot request envelope field 'payload' must be an object.")
    for payload_key in payload_value:
        if not isinstance(payload_key, str):
            raise ValidationError("Snapshot request payload keys must be strings.")
    return resource, snapshot_id, payload_value


def _coerce_snapshot_validation_exception(exception: BaseException) -> ValidationError:
    if isinstance(exception, ValidationError):
        return exception
    return ValidationError(str(exception), cause=exception)


def _handle_snapshot_validation_failure(
    exception: BaseException,
    *,
    resource: str,
    snapshot_id: str,
    trace_id: str | None,
    enqueue_warning_tracker: EnqueueWarningTracker,
    connection: WebsocketConnection,
) -> None:
    validation_error = _coerce_snapshot_validation_exception(exception)
    log_handled_exception(
        get_logger(LOGGER_NAME),
        validation_error,
        message="Snapshot request validation failed (non-critical).",
        operation=OPERATION,
        trace_id=trace_id,
        details={"resource": resource},
        level="debug",
    )
    send_snapshot_error_event(
        validation_error,
        resource,
        snapshot_id,
        trace_id,
        enqueue_warning_tracker,
        connection,
    )


async def handle_snapshot_request(
    data: JSONDict,
    connection: WebsocketConnection,
    websocket: WebSocket,
) -> None:
    resource_value = data.get("resource")
    resource = resource_value if isinstance(resource_value, str) else ""
    snapshot_id_value = data.get("snapshot_id")
    snapshot_id = snapshot_id_value.strip() if isinstance(snapshot_id_value, str) else ""
    trace_id = None
    try:
        ws_context = websocket.state.context
    except AttributeError:
        ws_context = None
    if ws_context is not None:
        try:
            trace_id = ws_context.trace_id
        except AttributeError:
            trace_id = None
    enqueue_warning_tracker = connection.api_context.dependencies.enqueue_warning_tracker
    try:
        resource, snapshot_id, handler_payload = _parse_snapshot_request_envelope(data)
        required_permission: AccessAction | None = None
        for allowed_resource, permission in SNAPSHOT_PERMISSION_RULES:
            if resource == allowed_resource:
                required_permission = permission
                break
        if not required_permission or required_permission not in connection.granted_actions:
            send_permission_error(
                resource,
                snapshot_id,
                trace_id,
                enqueue_warning_tracker,
                connection,
            )
            return
        handler = resolve_snapshot_handler(resource)
        if not handler:
            raise ValidationError(f"Unknown resource: {resource}")
        handler_snapshot_data: JSONValue = await handler(handler_payload, connection, websocket)
        response_event = build_snapshot_response_event(resource, snapshot_id, handler_snapshot_data)
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            response_event,
            f"WebSocket snapshot response to {connection.user.get('username', 'unknown')}",
        )
    except (ValidationError, pydantic.ValidationError) as exception:
        _handle_snapshot_validation_failure(
            exception,
            resource=resource,
            snapshot_id=snapshot_id,
            trace_id=trace_id,
            enqueue_warning_tracker=enqueue_warning_tracker,
            connection=connection,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Snapshot generation failed",
            operation=OPERATION,
            trace_id=trace_id,
            details={"resource": resource},
        )
        send_snapshot_error_event(
            exception,
            resource,
            snapshot_id,
            trace_id,
            enqueue_warning_tracker,
            connection,
        )
