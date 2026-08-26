"""SoAI - Snapshot dispatcher error event helpers [backend/features/api/routes/system/events/snapshots/error_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exceptions import SoAIError
from core.errors.payload import ErrorPublicPayload
from core.errors.public_projection import project_public_error
from features.api.routes.system.events.snapshots.payloads import (
    build_snapshot_error_event,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "send_permission_error",
    "send_snapshot_error_event",
)


def send_permission_error(
    resource: str,
    snapshot_id: str,
    trace_id: str | None,
    enqueue_warning_tracker: EnqueueWarningTracker,
    connection: WebsocketConnection,
) -> None:
    error_payload = ErrorPublicPayload(
        code="forbidden_error",
        message="Insufficient permissions",
        details={"resource": resource},
        trace_id=trace_id,
    ).to_dict()
    message_value = error_payload.get("message")
    message = str(message_value) if message_value is not None else None
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_snapshot_error_event(resource, snapshot_id, message, error_payload),
        "WebSocket snapshot error",
    )


def send_snapshot_error_event(
    exception: BaseException,
    resource: str,
    snapshot_id: str,
    trace_id: str | None,
    enqueue_warning_tracker: EnqueueWarningTracker,
    connection: WebsocketConnection,
) -> None:
    if isinstance(exception, SoAIError):
        error = exception
    else:
        error = coerce_to_soai_error(
            exception,
            code="server_error",
            trace_id=trace_id,
        )
    error_payload = project_public_error(error, trace_id=trace_id).to_dict()
    error_message_value = error_payload.get("message")
    error_message = str(error_message_value) if error_message_value is not None else None
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_snapshot_error_event(resource, snapshot_id, error_message, error_payload),
        "WebSocket snapshot error",
    )
