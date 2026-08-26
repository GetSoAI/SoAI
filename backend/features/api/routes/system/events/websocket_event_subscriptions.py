"""SoAI - WebSocket event subscription registration and delivery [backend/features/api/routes/system/events/websocket_event_subscriptions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.concurrency.queue_backpressure import (
    BackpressureDeliveryStatus,
    put_with_backpressure,
)
from core.concurrency.queue_ops import (
    QueueDropTracker,
    log_queue_drop_with_tracker,
)
from core.events.protocols import (
    ConvIdPartitionKeyProtocol,
    EventBusProtocol,
    EventWithDeliveryProtocol,
)
from core.events.types_base import Event, EventDelivery
from core.events.types_conversation_durable import (
    ConversationAttentionChangedEvent,
    ConversationInputTerminalEvent,
)
from core.events.types_system import (
    ChatStreamActivityChangedEvent,
    ChatStreamEvent,
    ModelTestStreamEvent,
    SoAIBenchRunUpdatedEvent,
)
from core.events.types_webui import (
    NotificationCreatedEvent,
    UserPasswordChangedEvent,
    UserSessionInvalidatedEvent,
    UserUsernameChangedEvent,
)
from core.logging.trace import get_logger
from core.notifications.notification_source_visibility import (
    notification_source_is_visible,
    resolve_notification_excluded_sources,
)
from core.state.access import AccessAction
from core.types.json import JSONDict
from features.api.routes.system.events.agent_event_types import (
    REALTIME_AGENT_ACTION_EVENT_TYPES,
    REALTIME_AGENT_DELTA_EVENT_TYPES,
)
from features.api.routes.system.events.permissions import (
    event_visible_to_user,
    resolve_current_user_id,
)
from features.api.routes.system.events.websocket_attachment_visibility import (
    attachment_event_visible_to_connection,
)
from features.api.routes.system.events.websocket_permission_refresh import (
    refresh_websocket_effective_actions,
)
from features.api.routes.system.events.websocket_permission_rules import (
    build_websocket_event_permission_rules,
)
from features.api.routes.system.events.websocket_resource_registry import (
    is_websocket_chat_presentation_event_type,
    is_websocket_resource_interest_event_type,
)
from features.api.routes.system.events.websocket_session_validation import (
    validate_websocket_session,
)
from features.api.runtime.container.enqueue_warning_tracker import EnqueueWarningTracker
from features.api.runtime.context import ApiContext
from features.api.runtime.event_enqueue import enqueue_event_or_warn
from features.api.streaming.event_payload_mapping import event_to_transport_payload
from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "reconcile_websocket_event_subscriptions",
    "register_websocket_event_subscriptions",
)

LOGGER_NAME = "SoAI.features.api.websocket_event_subscriptions"


_CRITICAL_CHRONOLOGY_EVENTS: frozenset[type[Event]] = frozenset(
    {
        ChatStreamEvent,
        ChatStreamActivityChangedEvent,
        ConversationAttentionChangedEvent,
        ConversationInputTerminalEvent,
        ModelTestStreamEvent,
        SoAIBenchRunUpdatedEvent,
    },
)

_AGENT_ACTION_BACKPRESSURE_TIMEOUT_SECONDS: float = 0.35
_CRITICAL_CHRONOLOGY_BACKPRESSURE_TIMEOUT_SECONDS: float = 0.75
_WEBSOCKET_SUBSCRIPTION_DROP_WARNING_INTERVAL_SECONDS: float = 30.0


def _notification_event_visible_to_connection(
    event: Event,
    connection: WebsocketConnection,
) -> bool:
    if not isinstance(event, NotificationCreatedEvent):
        return True
    excluded_sources = resolve_notification_excluded_sources(
        can_read_plugins=AccessAction.PLUGIN_READ in connection.granted_actions,
    )
    return notification_source_is_visible(event.source, excluded_sources)


async def _enqueue_critical_event_or_shutdown(
    *,
    connection: WebsocketConnection,
    event_data: JSONDict,
    queue_label: str,
    shutdown_event: asyncio.Event,
    drop_tracker: QueueDropTracker,
) -> None:
    await _enqueue_event_with_backpressure(
        connection=connection,
        event_data=event_data,
        queue_label=queue_label,
        shutdown_event=shutdown_event,
        backpressure_timeout=_CRITICAL_CHRONOLOGY_BACKPRESSURE_TIMEOUT_SECONDS,
        drop_tracker=drop_tracker,
    )


async def _enqueue_agent_action_event_or_shutdown(
    *,
    connection: WebsocketConnection,
    event_data: JSONDict,
    queue_label: str,
    shutdown_event: asyncio.Event,
    drop_tracker: QueueDropTracker,
) -> None:
    await _enqueue_event_with_backpressure(
        connection=connection,
        event_data=event_data,
        queue_label=queue_label,
        shutdown_event=shutdown_event,
        backpressure_timeout=_AGENT_ACTION_BACKPRESSURE_TIMEOUT_SECONDS,
        drop_tracker=drop_tracker,
    )


def _event_requires_critical_chronology(event: Event) -> bool:
    if type(event) not in _CRITICAL_CHRONOLOGY_EVENTS:
        return False
    if isinstance(event, EventWithDeliveryProtocol):
        return event.delivery == EventDelivery.MUST_DELIVER
    return True


async def _handle_session_invalidation_event(
    event: Event,
    connection: WebsocketConnection,
    shutdown_event: asyncio.Event,
) -> bool:
    if not isinstance(
        event,
        UserPasswordChangedEvent | UserUsernameChangedEvent | UserSessionInvalidatedEvent,
    ):
        return False
    if event.user_id != resolve_current_user_id(connection.user):
        return True
    if isinstance(event, UserPasswordChangedEvent | UserUsernameChangedEvent):
        if connection.jti not in event.revoked_session_jtis:
            return True
        if not await validate_websocket_session(connection, force=True):
            shutdown_event.set()
        return True
    if isinstance(event, UserSessionInvalidatedEvent):
        if event.session_jtis is None:
            shutdown_event.set()
            return True
        if connection.jti not in event.session_jtis:
            return True
    if not await validate_websocket_session(connection, force=True):
        shutdown_event.set()
    return True


async def _enqueue_event_with_backpressure(
    *,
    connection: WebsocketConnection,
    event_data: JSONDict,
    queue_label: str,
    shutdown_event: asyncio.Event,
    backpressure_timeout: float,
    drop_tracker: QueueDropTracker,
) -> None:
    result = await put_with_backpressure(
        connection.queue,
        event_data,
        shutdown_event,
        backpressure_timeout=backpressure_timeout,
    )
    if result.status in {
        BackpressureDeliveryStatus.DELIVERED,
        BackpressureDeliveryStatus.DELIVERED_AFTER_WAIT,
    }:
        return
    logger = get_logger(LOGGER_NAME)
    log_queue_drop_with_tracker(
        logger,
        drop_tracker,
        max(1, result.dropped_count),
        f"Failed to enqueue websocket event for {queue_label} due to queue backpressure",
    )
    shutdown_event.set()


def register_websocket_event_subscriptions(
    *,
    event_bus: EventBusProtocol,
    api_context: ApiContext,
    connection: WebsocketConnection,
    enqueue_warning_tracker: EnqueueWarningTracker,
    shutdown_event: asyncio.Event,
) -> Callable[[Event], Awaitable[None]]:
    drop_tracker = QueueDropTracker(_WEBSOCKET_SUBSCRIPTION_DROP_WARNING_INTERVAL_SECONDS)

    async def event_handler(event: Event) -> None:
        event_type = type(event)
        await refresh_websocket_effective_actions(connection)
        reconcile_websocket_event_subscriptions(
            event_bus=event_bus,
            connection=connection,
            event_handler=event_handler,
        )
        can_receive = connection.can_receive_event(event_type)
        if not can_receive:
            return
        if await _handle_session_invalidation_event(event, connection, shutdown_event):
            return
        if not event_visible_to_user(
            event,
            current_user=connection.user,
            files=api_context.dependencies.files,
            mcp_server=api_context.dependencies.mcp_server,
        ):
            return
        if not await attachment_event_visible_to_connection(event, connection=connection):
            return
        if not _notification_event_visible_to_connection(event, connection):
            return
        if event_type not in connection.subscribed_types:
            return
        if is_websocket_chat_presentation_event_type(event_type):
            selected_conversation_id = connection.chat_presentation_conversation_id
            if (
                selected_conversation_id is None
                or not isinstance(event, ConvIdPartitionKeyProtocol)
                or event.conv_id != selected_conversation_id
            ):
                return
        event_data = event_to_transport_payload(event)
        queue_label = f"WebSocket for {connection.user.get('username', 'unknown')}"
        if _event_requires_critical_chronology(event):
            await _enqueue_critical_event_or_shutdown(
                connection=connection,
                event_data=event_data,
                queue_label=queue_label,
                shutdown_event=shutdown_event,
                drop_tracker=drop_tracker,
            )
            return
        if event_type in REALTIME_AGENT_ACTION_EVENT_TYPES:
            await _enqueue_agent_action_event_or_shutdown(
                connection=connection,
                event_data=event_data,
                queue_label=queue_label,
                shutdown_event=shutdown_event,
                drop_tracker=drop_tracker,
            )
            return
        if event_type in REALTIME_AGENT_DELTA_EVENT_TYPES:
            enqueue_event_or_warn(
                enqueue_warning_tracker,
                connection.queue,
                event_data,
                queue_label,
            )
            return
        enqueue_event_or_warn(enqueue_warning_tracker, connection.queue, event_data, queue_label)

    reconcile_websocket_event_subscriptions(
        event_bus=event_bus,
        connection=connection,
        event_handler=event_handler,
    )

    get_logger(LOGGER_NAME).debug(
        "Registered %s WebSocket event subscriptions for %s.",
        len(connection.subscribed_types),
        connection.user.get("username", "unknown"),
    )
    return event_handler


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
