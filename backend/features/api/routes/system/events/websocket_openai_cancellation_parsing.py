"""SoAI - WebSocket OpenAI cancellation payload parsing [backend/features/api/routes/system/events/websocket_openai_cancellation_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.state.access import AccessAction

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.streaming.websocket import WebsocketConnection

__all__ = ("try_parse_openai_ws_cancel_request",)


def try_parse_openai_ws_cancel_request(
    data: JSONDict,
    *,
    connection: WebsocketConnection,
    require_run_id: Callable[[JSONDict], str],
) -> tuple[str, str] | None:
    if AccessAction.OPENAI_API not in connection.granted_actions:
        return None
    try:
        run_id = require_run_id(data)
    except ValidationError:
        return None
    reason_value = data.get("reason")
    reason = (
        reason_value.strip()
        if isinstance(reason_value, str) and reason_value.strip()
        else "Cancelled."
    )
    return run_id, reason
