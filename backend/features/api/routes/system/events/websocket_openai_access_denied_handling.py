"""SoAI - WebSocket OpenAI access denied handling [backend/features/api/routes/system/events/websocket_openai_access_denied_handling.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.state.access import AccessAction
from features.api.routes.system.events.websocket_errors import enqueue_websocket_error
from features.api.routes.system.events.websocket_run_payloads import resolve_run_id
from features.api.runtime.event_enqueue import enqueue_event_or_warn

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.container.enqueue_warning_tracker import (
        EnqueueWarningTracker,
    )
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("handle_openai_ws_access_denied",)


async def handle_openai_ws_access_denied(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    trace_id: str | None,
    error_event_type: str,
    build_forbidden_error_payload: Callable[..., JSONDict],
    warn_label: str,
) -> bool:
    if AccessAction.OPENAI_API in connection.granted_actions:
        return False
    run_id = resolve_run_id(data)
    if run_id is not None:
        enqueue_event_or_warn(
            enqueue_warning_tracker,
            connection.queue,
            build_forbidden_error_payload(
                run_id=run_id,
                message="Insufficient permissions.",
                code="forbidden_error",
            ),
            warn_label,
        )
        return True
    await enqueue_websocket_error(
        enqueue_warning_tracker,
        connection.queue,
        trace_id,
        error_event_type,
        "Insufficient permissions.",
        code="forbidden_error",
    )
    return True
