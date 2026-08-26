"""SoAI - WebSocket forward-task cancellation ID helpers [backend/features/api/routes/system/events/websocket_cancellation_ids.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.api.runtime.request_cancellation import (
    resolve_request_cancellation_id_or_create,
)
from features.api.streaming.websocket import WebsocketConnection

__all__ = ("resolve_connection_cancellation_id_or_create",)


def resolve_connection_cancellation_id_or_create(
    connection: WebsocketConnection,
    *,
    subsystem: str,
    trace_id: str | None,
    owner: str,
) -> str:
    return resolve_request_cancellation_id_or_create(
        connection.request,
        subsystem=subsystem,
        trace_id=trace_id,
        owner=owner,
    )
