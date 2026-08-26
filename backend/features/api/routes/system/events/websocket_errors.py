"""SoAI - WebSocket error event helpers for system events [backend/features/api/routes/system/events/websocket_errors.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import SoAIError
from core.errors.http_status_classification import (
    resolve_soai_error_code_for_http_status,
)
from core.errors.public_projection import project_public_error
from features.api.routes.system.events.internal_protocols import WebSocketEventTypes
from features.api.routes.system.events.websocket_error_payloads import (
    build_websocket_error_event,
    resolve_websocket_error_type_for_soai_code,
)
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "enqueue_connection_server_error",
    "enqueue_connection_soai_error",
    "enqueue_pty_websocket_error",
    "enqueue_pty_websocket_server_error",
    "enqueue_pty_websocket_soai_error",
    "enqueue_websocket_error",
    "enqueue_websocket_forbidden_error",
    "enqueue_websocket_invalid_request_error",
    "enqueue_websocket_not_found_error",
    "enqueue_websocket_soai_error",
)


async def enqueue_websocket_error(
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[JSONDict],
    trace_id: str | None,
    error_type: str,
    message: str,
    *,
    code: str = "server_error",
    task_id: str | None = None,
    details: JSONDict | None = None,
    run_id: str | None = None,
) -> None:
    payload = build_websocket_error_event(
        trace_id=trace_id,
        error_type=error_type,
        message=message,
        code=code,
        task_id=task_id,
        details=details,
        run_id=run_id,
    )
    enqueue_event_or_warn(enqueue_warning_tracker, queue, payload, "WebSocket error")


async def enqueue_pty_websocket_error(
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[JSONDict],
    trace_id: str | None,
    message: str,
    *,
    code: str,
) -> None:
    await enqueue_websocket_error(
        enqueue_warning_tracker,
        queue,
        trace_id,
        WebSocketEventTypes.PTY_ERROR,
        message,
        code=code,
    )


async def enqueue_pty_websocket_soai_error(
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[JSONDict],
    trace_id: str | None,
    exception: SoAIError,
) -> None:
    public_payload = project_public_error(exception, trace_id=trace_id)
    await enqueue_pty_websocket_error(
        enqueue_warning_tracker,
        queue,
        trace_id,
        public_payload.message,
        code=str(public_payload.code),
    )


async def enqueue_pty_websocket_server_error(
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[JSONDict],
    trace_id: str | None,
) -> None:
    await enqueue_pty_websocket_error(
        enqueue_warning_tracker,
        queue,
        trace_id,
        "Internal server error.",
        code="server_error",
    )


async def enqueue_websocket_soai_error(
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[JSONDict],
    trace_id: str | None,
    exception: SoAIError,
    *,
    task_id: str | None = None,
    run_id: str | None = None,
) -> None:
    public_payload = project_public_error(exception, trace_id=trace_id)
    error_code = resolve_soai_error_code_for_http_status(exception.http_status)
    await enqueue_websocket_error(
        enqueue_warning_tracker,
        queue,
        trace_id,
        resolve_websocket_error_type_for_soai_code(error_code),
        public_payload.message,
        code=str(public_payload.code),
        details=(dict(public_payload.details) if public_payload.details is not None else None),
        task_id=task_id,
        run_id=run_id,
    )


async def enqueue_connection_soai_error(
    enqueue_warning_tracker: EnqueueWarningTracker,
    connection: WebsocketConnection,
    trace_id: str | None,
    exception: SoAIError,
    *,
    task_id: str | None = None,
    run_id: str | None = None,
) -> None:
    await enqueue_websocket_soai_error(
        enqueue_warning_tracker,
        connection.queue,
        trace_id,
        exception,
        task_id=task_id,
        run_id=run_id,
    )


async def enqueue_connection_server_error(
    enqueue_warning_tracker: EnqueueWarningTracker,
    connection: WebsocketConnection,
    trace_id: str | None,
    *,
    task_id: str | None = None,
    run_id: str | None = None,
) -> None:
    await enqueue_websocket_error(
        enqueue_warning_tracker,
        connection.queue,
        trace_id,
        WebSocketEventTypes.SERVER_ERROR,
        "Internal server error.",
        code="server_error",
        task_id=task_id,
        run_id=run_id,
    )


async def enqueue_websocket_forbidden_error(
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[JSONDict],
    trace_id: str | None,
    *,
    run_id: str | None = None,
) -> None:
    await enqueue_websocket_error(
        enqueue_warning_tracker,
        queue,
        trace_id,
        WebSocketEventTypes.FORBIDDEN,
        "Insufficient permissions.",
        code="forbidden_error",
        run_id=run_id,
    )


async def enqueue_websocket_invalid_request_error(
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[JSONDict],
    trace_id: str | None,
    message: str,
    *,
    run_id: str | None = None,
) -> None:
    await enqueue_websocket_error(
        enqueue_warning_tracker,
        queue,
        trace_id,
        WebSocketEventTypes.INVALID_REQUEST,
        message,
        code="invalid_request_error",
        run_id=run_id,
    )


async def enqueue_websocket_not_found_error(
    enqueue_warning_tracker: EnqueueWarningTracker,
    queue: asyncio.Queue[JSONDict],
    trace_id: str | None,
    message: str,
    *,
    run_id: str | None = None,
) -> None:
    await enqueue_websocket_error(
        enqueue_warning_tracker,
        queue,
        trace_id,
        WebSocketEventTypes.NOT_FOUND,
        message,
        code="not_found_error",
        run_id=run_id,
    )
