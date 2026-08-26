"""SoAI - Domain event outbox payload decoding [backend/app/background/domain_event_outbox_decoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.background.domain_event_outbox_conversation_decoding import (
    decode_conversation_outbox_event,
)
from app.background.domain_event_outbox_notification_decoding import (
    decode_notification_outbox_event,
)
from app.background.outbox_payload_parsing import (
    coerce_outbox_bool,
    coerce_outbox_int,
    coerce_outbox_optional_str,
    coerce_outbox_str,
    coerce_outbox_str_tuple,
    parse_outbox_payload_object,
    require_positive_outbox_timestamp_seconds,
)
from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.events.types_plugins import (
    PluginLoadedEvent,
    ProviderDiscoveryRequestedEvent,
    ProviderStatusUpdatedEvent,
)
from core.events.types_system import TriggerConfigReconciliationCommand
from core.events.types_tasks import TaskCompleteEvent
from core.events.types_webui import (
    AutomationCreatedEvent,
    AutomationDeletedEvent,
    AutomationRunCreatedEvent,
    AutomationRunUpdatedEvent,
    AutomationUpdatedEvent,
    LicensingStatusChangedEvent,
    UserCreatedEvent,
    UserDeletedEvent,
    UserPasswordChangedEvent,
    UserRoleChangedEvent,
    UserSessionInvalidatedEvent,
    UserUsernameChangedEvent,
)
from core.validation.object_fields import require_exact_json_fields

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("decode_outbox_event",)


def _decode_automation_event(
    *,
    decoded: dict[str, JSONValue],
    event_type: str,
    event_id: str,
    timestamp: float,
) -> Event:
    user_id = coerce_outbox_int(decoded.get("user_id"), label="user_id")
    automation_id = coerce_outbox_str(decoded.get("automation_id"), label="automation_id")
    if event_type == "AutomationCreatedEvent":
        return AutomationCreatedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            automation_id=automation_id,
        )
    if event_type == "AutomationUpdatedEvent":
        return AutomationUpdatedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            automation_id=automation_id,
        )
    if event_type == "AutomationDeletedEvent":
        return AutomationDeletedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            automation_id=automation_id,
        )
    run_id = coerce_outbox_str(decoded.get("run_id"), label="run_id")
    if event_type == "AutomationRunCreatedEvent":
        return AutomationRunCreatedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            automation_id=automation_id,
            run_id=run_id,
        )
    if event_type == "AutomationRunUpdatedEvent":
        return AutomationRunUpdatedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            automation_id=automation_id,
            run_id=run_id,
        )
    raise ValidationError(f"Unsupported outbox event_type: {event_type}")


def decode_outbox_event(event_type: str, payload_json: str) -> Event:
    decoded = parse_outbox_payload_object(payload_json)
    event_id = coerce_outbox_str(decoded.get("event_id"), label="event_id")
    timestamp = require_positive_outbox_timestamp_seconds(
        decoded.get("timestamp"),
        error_message="timestamp must be a positive number.",
    )
    if event_type.startswith("Conversation"):
        return decode_conversation_outbox_event(
            decoded=decoded,
            event_type=event_type,
            event_id=event_id,
            timestamp=timestamp,
        )
    if event_type.startswith("Automation"):
        return _decode_automation_event(
            decoded=decoded,
            event_type=event_type,
            event_id=event_id,
            timestamp=timestamp,
        )
    if event_type.startswith("Notification") or event_type.startswith("Notifications"):
        return decode_notification_outbox_event(
            decoded=decoded,
            event_type=event_type,
            event_id=event_id,
            timestamp=timestamp,
        )
    if event_type == "LicensingStatusChangedEvent":
        require_exact_json_fields(
            decoded,
            allowed_fields=frozenset(("event_id", "timestamp")),
            label="Licensing status changed event",
        )
        return LicensingStatusChangedEvent(event_id=event_id, timestamp=timestamp)
    if event_type == "ProviderStatusUpdatedEvent":
        plugin_name = coerce_outbox_str(decoded.get("plugin_name"), label="plugin_name")
        provider_id = coerce_outbox_str(decoded.get("provider_id"), label="provider_id")
        new_status = coerce_outbox_str(decoded.get("new_status"), label="new_status")
        error_value = decoded.get("error")
        if error_value is not None and not isinstance(error_value, str):
            raise ValidationError("error must be a string or null")
        return ProviderStatusUpdatedEvent(
            event_id=event_id,
            timestamp=timestamp,
            plugin_name=plugin_name,
            provider_id=provider_id,
            new_status=new_status,
            error=error_value,
        )
    if event_type == "ProviderDiscoveryRequestedEvent":
        plugin_name = coerce_outbox_str(decoded.get("plugin_name"), label="plugin_name")
        provider_id = coerce_outbox_str(decoded.get("provider_id"), label="provider_id")
        provider_revision = coerce_outbox_int(
            decoded.get("provider_revision"),
            label="provider_revision",
        )
        if provider_revision < 0:
            raise ValidationError("provider_revision must be non-negative")
        return ProviderDiscoveryRequestedEvent(
            event_id=event_id,
            timestamp=timestamp,
            plugin_name=plugin_name,
            provider_id=provider_id,
            provider_revision=provider_revision,
        )
    if event_type == "PluginLoadedEvent":
        plugin_name = coerce_outbox_str(decoded.get("plugin_name"), label="plugin_name")
        return PluginLoadedEvent(
            plugin_name=plugin_name,
            event_id=event_id,
            timestamp=timestamp,
        )
    if event_type == "TriggerConfigReconciliationCommand":
        reason = coerce_outbox_str(decoded.get("reason"), label="reason")
        return TriggerConfigReconciliationCommand(
            reason=reason,
            context=None,
            event_id=event_id,
            timestamp=timestamp,
        )
    if event_type == "TaskCompleteEvent":
        error_code_value = decoded.get("error_code")
        return TaskCompleteEvent(
            event_id=event_id,
            timestamp=timestamp,
            success=coerce_outbox_bool(decoded.get("success"), label="success"),
            message=coerce_outbox_str(decoded.get("message"), label="message"),
            task_id=coerce_outbox_str(decoded.get("task_id"), label="task_id"),
            user_id=coerce_outbox_int(decoded.get("user_id"), label="user_id"),
            status=coerce_outbox_str(decoded.get("status"), label="status"),
            error_code=(
                None
                if error_code_value is None
                else coerce_outbox_int(error_code_value, label="error_code")
            ),
            error_type=coerce_outbox_optional_str(
                decoded.get("error_type"),
                label="error_type",
            ),
            error_message=coerce_outbox_optional_str(
                decoded.get("error_message"),
                label="error_message",
            ),
        )
    user_id = coerce_outbox_int(decoded.get("user_id"), label="user_id")
    username = coerce_outbox_str(decoded.get("username"), label="username")
    if event_type == "UserCreatedEvent":
        is_admin = coerce_outbox_bool(decoded.get("is_admin"), label="is_admin")
        return UserCreatedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            username=username,
            is_admin=bool(is_admin),
            identity_revision=coerce_outbox_int(
                decoded.get("identity_revision"),
                label="identity_revision",
            ),
        )
    if event_type == "UserPasswordChangedEvent":
        revoked_session_jtis = coerce_outbox_str_tuple(
            decoded.get("revoked_session_jtis"),
            label="revoked_session_jtis",
        )
        rotation_source_jti = coerce_outbox_optional_str(
            decoded.get("rotation_source_jti"),
            label="rotation_source_jti",
        )
        return UserPasswordChangedEvent(
            event_id=event_id,
            timestamp=timestamp,
            operation_id=coerce_outbox_str(decoded.get("operation_id"), label="operation_id"),
            actor_user_id=coerce_outbox_int(
                decoded.get("actor_user_id"),
                label="actor_user_id",
            ),
            user_id=int(user_id),
            username=username,
            revoked_session_jtis=revoked_session_jtis,
            rotation_source_jti=rotation_source_jti,
            password_revision=coerce_outbox_int(
                decoded.get("password_revision"),
                label="password_revision",
            ),
        )
    if event_type == "UserUsernameChangedEvent":
        return UserUsernameChangedEvent(
            event_id=event_id,
            timestamp=timestamp,
            operation_id=coerce_outbox_str(decoded.get("operation_id"), label="operation_id"),
            actor_user_id=coerce_outbox_int(
                decoded.get("actor_user_id"),
                label="actor_user_id",
            ),
            user_id=int(user_id),
            previous_username=coerce_outbox_str(
                decoded.get("previous_username"),
                label="previous_username",
            ),
            username=username,
            identity_revision=coerce_outbox_int(
                decoded.get("identity_revision"),
                label="identity_revision",
            ),
            revoked_session_jtis=coerce_outbox_str_tuple(
                decoded.get("revoked_session_jtis"),
                label="revoked_session_jtis",
            ),
            rotation_source_jti=coerce_outbox_optional_str(
                decoded.get("rotation_source_jti"),
                label="rotation_source_jti",
            ),
        )
    if event_type == "UserDeletedEvent":
        return UserDeletedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            username=username,
        )
    if event_type == "UserSessionInvalidatedEvent":
        return UserSessionInvalidatedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            username=username,
            reason=coerce_outbox_str(decoded.get("reason"), label="reason"),
            session_jtis=coerce_outbox_str_tuple(
                decoded.get("session_jtis"),
                label="session_jtis",
            ),
        )
    if event_type == "UserRoleChangedEvent":
        is_admin = coerce_outbox_bool(decoded.get("is_admin"), label="is_admin")
        return UserRoleChangedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            username=username,
            is_admin=bool(is_admin),
            identity_revision=coerce_outbox_int(
                decoded.get("identity_revision"),
                label="identity_revision",
            ),
        )
    raise ValidationError(f"Unsupported outbox event_type: {event_type}")
