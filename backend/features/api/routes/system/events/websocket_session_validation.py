"""SoAI - WebSocket session revalidation [backend/features/api/routes/system/events/websocket_session_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time

from core.timing.epoch import epoch_ms
from core.users.user_id import require_strict_user_id
from features.api.streaming.websocket import WebsocketConnection

__all__ = ("set_websocket_session_closure", "validate_websocket_session")

_REVALIDATION_INTERVAL_SECONDS = 300.0
_SESSION_CLOSE_CODE = 4001
_SESSION_REVOKED_CLOSE_REASON = "session_revoked"
_SESSION_ROTATED_CLOSE_REASON = "session_rotated"


def set_websocket_session_closure(
    connection: WebsocketConnection,
    *,
    rotated: bool,
) -> None:
    connection.close_code = _SESSION_CLOSE_CODE
    connection.close_reason = (
        _SESSION_ROTATED_CLOSE_REASON if rotated else _SESSION_REVOKED_CLOSE_REASON
    )


async def validate_websocket_session(
    connection: WebsocketConnection,
    *,
    force: bool,
) -> bool:
    now_monotonic = time.monotonic()
    if not force and now_monotonic < connection.session_revalidation_deadline:
        return True
    username_value = connection.user.get("username")
    username = username_value if isinstance(username_value, str) else None
    state = await connection.api_context.dependencies.webui_manager.database_tokens.read_token_auth_state(
        jti=connection.jti,
        user_id=require_strict_user_id(connection.user.get("id")),
        username=username,
    )
    if state.status != "active" or state.user is None:
        set_websocket_session_closure(
            connection,
            rotated=state.status == "session_rotated",
        )
        return False
    await connection.api_context.dependencies.webui_manager.database_tokens.touch_session(
        jti=connection.jti,
        observed_at_ms=epoch_ms(),
    )
    connection.session_revalidation_deadline = now_monotonic + _REVALIDATION_INTERVAL_SECONDS
    return True
