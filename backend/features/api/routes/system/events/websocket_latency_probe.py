"""SoAI - WebSocket latency probe handling [backend/features/api/routes/system/events/websocket_latency_probe.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from core.errors.exceptions import ValidationError
from core.system_api.websocket_payloads import build_websocket_event_payload
from core.validation.strings import coerce_required_non_empty_str
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_errors import (
    enqueue_websocket_invalid_request_error,
)
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.routes.system.events.websocket_event_context import (
        WebsocketEventRuntimeContext,
    )

__all__ = ("handle_latency_probe_message",)

MAX_LATENCY_PROBE_ID_LENGTH: Final[int] = 128


async def handle_latency_probe_message(
    data: JSONDict,
    *,
    runtime_context: WebsocketEventRuntimeContext,
) -> None:
    try:
        probe_id = coerce_required_non_empty_str(data.get("probe_id"), label="Latency probe id")
    except ValidationError as exception:
        await enqueue_websocket_invalid_request_error(
            runtime_context.enqueue_warning_tracker,
            runtime_context.connection.queue,
            runtime_context.trace_id,
            exception.message,
        )
        return
    if len(probe_id) > MAX_LATENCY_PROBE_ID_LENGTH:
        await enqueue_websocket_invalid_request_error(
            runtime_context.enqueue_warning_tracker,
            runtime_context.connection.queue,
            runtime_context.trace_id,
            f"Latency probe id must be at most {MAX_LATENCY_PROBE_ID_LENGTH} characters.",
        )
        return
    enqueue_event_or_warn(
        runtime_context.enqueue_warning_tracker,
        runtime_context.connection.queue,
        build_websocket_event_payload(
            WebSocketEventTypes.LATENCY_PROBE_RESULT,
            {"probe_id": probe_id},
        ),
        "WebSocket latency probe",
    )
