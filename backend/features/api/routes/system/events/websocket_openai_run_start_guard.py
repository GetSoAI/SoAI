"""SoAI - WebSocket OpenAI run start guarding [backend/features/api/routes/system/events/websocket_openai_run_start_guard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from features.api.routes.system.events.websocket_errors import enqueue_websocket_error
from features.api.routes.system.events.websocket_openai_access_denied_handling import (
    handle_openai_ws_access_denied,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("guard_openai_ws_run_start",)


async def guard_openai_ws_run_start(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    error_event_type: str,
    build_forbidden_error_payload: Callable[..., JSONDict],
    warn_label: str,
    require_run_id: Callable[[JSONDict], str],
) -> str | None:
    denied = await handle_openai_ws_access_denied(
        data,
        connection=connection,
        enqueue_warning_tracker=enqueue_warning_tracker,
        trace_id=trace_id,
        error_event_type=error_event_type,
        build_forbidden_error_payload=build_forbidden_error_payload,
        warn_label=warn_label,
    )
    if denied:
        return None
    try:
        return require_run_id(data)
    except ValidationError as exception:
        await enqueue_websocket_error(
            enqueue_warning_tracker,
            connection.queue,
            trace_id,
            error_event_type,
            exception.message,
            code="invalid_request_error",
        )
        return None
