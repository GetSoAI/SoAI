"""SoAI - Current WebSocket effective-action refresh [backend/features/api/routes/system/events/websocket_permission_refresh.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.api.middleware.acl_enforcement import resolve_request_effective_actions
from features.api.streaming.websocket import WebsocketConnection

__all__ = ("refresh_websocket_effective_actions",)


async def refresh_websocket_effective_actions(
    connection: WebsocketConnection,
) -> None:
    connection.request.state.effective_access_actions = None
    connection.granted_actions = await resolve_request_effective_actions(connection.request)
