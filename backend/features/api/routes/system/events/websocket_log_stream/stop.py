"""SoAI - WebSocket log stream stop logic [backend/features/api/routes/system/events/websocket_log_stream/stop.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.logging.trace import get_logger
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_errors import enqueue_websocket_error
from features.api.routes.system.events.websocket_log_stream.events import (
    build_log_stream_unsubscribed_payload,
)
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.runtime.log_source_resolution import resolve_log_source_name
from features.api.streaming.websocket import WebsocketConnection

__all__ = ("stop_log_stream",)

LOGGER_NAME = "SoAI.features.api.stop"


async def stop_log_stream(
    source_name: str,
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    emit_event: bool = True,
    suppress_closed_event: bool = False,
) -> None:
    normalized = (source_name or "").strip()
    if not normalized:
        error_message = "source_name is required to unsubscribe."
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            WebSocketEventTypes.LOG_STREAM_ERROR,
            error_message,
            code="invalid_request_error",
        )
        return
    resolved_source_name = resolve_log_source_name(connection.api_context.dependencies, normalized)
    existing = connection.log_streams.pop(resolved_source_name, None)
    if existing is None:
        return
    if existing is not None and not existing.done():
        if suppress_closed_event:
            connection.log_stream_replacements.add(resolved_source_name)
        try:
            await uncancel_then_cleanup(
                cancel_and_await(
                    [existing],
                    logger=get_logger(LOGGER_NAME),
                    task_label="websocket log stream forward task",
                    log_level=logging.DEBUG,
                    timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
                    timeout_log_level=logging.DEBUG,
                ),
            )
        finally:
            if suppress_closed_event:
                connection.log_stream_replacements.discard(resolved_source_name)
    if not emit_event:
        return
    enqueue_event_or_warn(
        enqueue_warning_tracker,
        connection.queue,
        build_log_stream_unsubscribed_payload(resolved_source_name),
        "WebSocket log stream unsubscribed",
    )
