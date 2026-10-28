"""SoAI - Current WebSocket effective-action refresh and permission-driven subscription reconciliation [backend/features/api/routes/system/events/websocket_permission_refresh.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.timing.constants import STANDARD_DELAY_SEC
from features.api.middleware.acl_enforcement import resolve_request_effective_actions
from features.api.routes.system.events.websocket_permission_rules import (
    build_websocket_event_permission_rules,
)
from features.api.routes.system.events.websocket_resource_registry import (
    is_websocket_resource_interest_event_type,
)
from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "reconcile_websocket_event_subscriptions",
    "refresh_websocket_effective_actions",
    "refresh_websocket_event_subscriptions",
)


async def refresh_websocket_effective_actions(
    connection: WebsocketConnection,
    *,
    force: bool,
) -> bool:
    now_monotonic = time.monotonic()
    if not force and now_monotonic < connection.effective_actions_refresh_deadline:
        return False
    connection.effective_actions_refresh_deadline = now_monotonic + STANDARD_DELAY_SEC
    previous_actions = connection.granted_actions
    connection.granted_actions = await connection.authorization.resolve(
        lambda: resolve_request_effective_actions(connection.request)
    )
    return connection.granted_actions != previous_actions


async def refresh_websocket_event_subscriptions(
    *,
    event_bus: EventBusProtocol,
    connection: WebsocketConnection,
    event_handler: Callable[[Event], Awaitable[None]] | None,
    force: bool,
) -> None:
    actions_changed = await refresh_websocket_effective_actions(connection, force=force)
    if not actions_changed or event_handler is None:
        return
    reconcile_websocket_event_subscriptions(
        event_bus=event_bus,
        connection=connection,
        event_handler=event_handler,
    )


def reconcile_websocket_event_subscriptions(
    *,
    event_bus: EventBusProtocol,
    connection: WebsocketConnection,
    event_handler: Callable[[Event], Awaitable[None]],
) -> None:
    for event_type, required_action in build_websocket_event_permission_rules():
        if is_websocket_resource_interest_event_type(event_type):
            continue
        permitted = required_action in connection.granted_actions
        subscribed = event_type in connection.subscribed_types
        if permitted and not subscribed:
            event_bus.subscribe(event_type, event_handler)
            connection.subscribed_types.add(event_type)
        elif not permitted and subscribed:
            event_bus.unsubscribe(event_type, event_handler)
            connection.subscribed_types.discard(event_type)
