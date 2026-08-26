"""SoAI - Plugin circuit breaker WebUI notification service [backend/app/background/plugin_circuit_breaker_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import EventBusProtocol
from core.events.types_base import Event
from core.events.types_plugins import CircuitBreakerStateChangedEvent
from core.logging.trace import get_logger
from core.notifications.notification_contracts import (
    PLUGIN_CIRCUIT_BREAKER_NOTIFICATION_SOURCE,
    NotificationLinkType,
    NotificationTemplateId,
    NotificationType,
)
from core.notifications.notification_record_models import NotificationLink
from core.notifications.notification_text_models import notification_text_from_template
from core.notifications.protocols_database import DatabaseNotificationsProtocol
from core.plugins.protocols_database import DatabasePluginsProtocol
from core.state.access import AccessAction, AccessState
from core.state.access_policy_overrides import (
    load_access_policy_overrides,
    merge_access_policy,
)
from core.state.circuit_breaker import CircuitBreakerState
from core.users.protocols_database import DatabaseUsersProtocol
from core.validation.integers import is_strict_int
from core.validation.strings import coerce_optional_trimmed_str

__all__ = (
    "PluginCircuitBreakerNotificationService",
    "PluginCircuitBreakerNotificationServiceDependencies",
)

LOGGER_NAME = "SoAI.app.background.plugin_circuit_breaker_notifications"
OPERATION_DELIVER = "plugin_circuit_breaker_notifications.deliver"
OPERATION_POLICY = "plugin_circuit_breaker_notifications.policy"
OPERATION_SHUTDOWN = "plugin_circuit_breaker_notifications.shutdown"
PLUGINS_ROUTE = "plugins"
REQUIRED_ACTIONS = frozenset({AccessAction.NOTIFICATIONS, AccessAction.PLUGIN_READ})


@dataclass(frozen=True, slots=True)
class PluginCircuitBreakerNotificationServiceDependencies:
    event_bus: EventBusProtocol
    database_plugins: DatabasePluginsProtocol
    database_users: DatabaseUsersProtocol
    database_notifications: DatabaseNotificationsProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="PluginCircuitBreakerNotificationServiceDependencies",
            database_notifications=self.database_notifications,
            database_plugins=self.database_plugins,
            database_users=self.database_users,
            event_bus=self.event_bus,
        )


class PluginCircuitBreakerNotificationService:
    def __init__(self, deps: PluginCircuitBreakerNotificationServiceDependencies) -> None:
        self._deps = deps
        self._logger = get_logger(LOGGER_NAME)
        self._handler: Callable[[Event], Awaitable[None]] = self._handle_event
        self._subscribed = False

    async def start(self) -> None:
        if self._subscribed:
            return
        self._deps.event_bus.subscribe(CircuitBreakerStateChangedEvent, self._handler)
        self._subscribed = True

    async def shutdown(self) -> None:
        if not self._subscribed:
            return
        try:
            self._deps.event_bus.unsubscribe(CircuitBreakerStateChangedEvent, self._handler)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                self._logger,
                exception,
                message=(
                    "Failed to unsubscribe plugin circuit breaker notification service "
                    "(non-critical)."
                ),
                operation=OPERATION_SHUTDOWN,
                level="warning",
            )
            return
        self._subscribed = False

    async def _handle_event(self, event: Event) -> None:
        if not isinstance(event, CircuitBreakerStateChangedEvent):
            return
        if event.state != CircuitBreakerState.OPEN.value or not event.is_open:
            return
        plugin_name = coerce_optional_trimmed_str(event.plugin_name)
        if plugin_name is None:
            return
        try:
            overrides = await load_access_policy_overrides(self._deps.database_plugins)
            policy = merge_access_policy(overrides)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Failed to resolve access policy for plugin circuit breaker notification.",
                operation=OPERATION_POLICY,
                level="warning",
                details={"plugin_name": plugin_name},
            )
            return
        try:
            users = await self._deps.database_users.list_human_users()
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Failed to list users for plugin circuit breaker notification.",
                operation=OPERATION_POLICY,
                level="warning",
                details={"plugin_name": plugin_name},
            )
            return
        link = NotificationLink(link_type=NotificationLinkType.URL, value=PLUGINS_ROUTE)
        title = notification_text_from_template(
            NotificationTemplateId.PLUGIN_CIRCUIT_BREAKER_TRIPPED_TITLE,
        )
        message = notification_text_from_template(
            NotificationTemplateId.PLUGIN_CIRCUIT_BREAKER_TRIPPED_MESSAGE,
            {"pluginName": plugin_name},
        )
        for user in users:
            user_id_value = user.get("id")
            if not is_strict_int(user_id_value) or int(user_id_value) <= 0:
                continue
            state = AccessState.ADMIN if user.get("is_admin") is True else AccessState.STANDARD
            actions = policy.get(state, frozenset())
            if not REQUIRED_ACTIONS.issubset(actions):
                continue
            try:
                await self._deps.database_notifications.create_notification(
                    int(user_id_value),
                    NotificationType.WARNING,
                    title,
                    message,
                    source=PLUGIN_CIRCUIT_BREAKER_NOTIFICATION_SOURCE,
                    link=link,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    self._logger,
                    exception,
                    message="Failed to create plugin circuit breaker notification.",
                    operation=OPERATION_DELIVER,
                    level="warning",
                    details={"plugin_name": plugin_name, "user_id": int(user_id_value)},
                )
