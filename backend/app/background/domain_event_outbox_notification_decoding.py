"""SoAI - Notification outbox payload decoding [backend/app/background/domain_event_outbox_notification_decoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic

from app.background.outbox_payload_parsing import (
    coerce_outbox_int,
    coerce_outbox_optional_str,
    coerce_outbox_str,
)
from core.errors.exceptions import ValidationError
from core.events.types_base import Event
from core.events.types_webui import (
    NotificationCreatedEvent,
    NotificationDeletedEvent,
    NotificationsClearedEvent,
    NotificationsMarkedReadEvent,
)
from core.notifications.notification_contracts import NOTIFICATION_TYPE_SQL_VALUES
from core.notifications.notification_record_models import NotificationLink
from core.notifications.notification_text_models import (
    NotificationTextPlain,
    NotificationTextTemplate,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("decode_notification_outbox_event",)


def _decode_notification_text(
    value: JSONValue,
    *,
    label: str,
) -> JSONValue:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} payload shape is invalid.")
    try:
        text_type = value.get("text_type")
        if text_type == "text":
            text_obj = NotificationTextPlain.model_validate(value)
            return text_obj.model_dump(mode="json")
        if text_type == "template":
            template_obj = NotificationTextTemplate.model_validate(value)
            return template_obj.model_dump(mode="json")
        raise ValidationError(f"{label} payload shape is invalid.")
    except pydantic.ValidationError as exception:
        raise ValidationError(f"{label} payload shape is invalid.") from exception


def decode_notification_outbox_event(
    *,
    decoded: dict[str, JSONValue],
    event_type: str,
    event_id: str,
    timestamp: float,
) -> Event:
    user_id = coerce_outbox_int(decoded.get("user_id"), label="user_id")
    if event_type == "NotificationsClearedEvent":
        return NotificationsClearedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
        )
    if event_type == "NotificationsMarkedReadEvent":
        notification_ids_value = decoded.get("notification_ids")
        if not isinstance(notification_ids_value, list):
            raise ValidationError("notification_ids must be an array.")
        notification_ids: list[str] = []
        for index, notification_id_value in enumerate(notification_ids_value):
            notification_ids.append(
                coerce_outbox_str(notification_id_value, label=f"notification_ids[{index}]"),
            )
        return NotificationsMarkedReadEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            notification_ids=notification_ids,
        )
    notification_id = coerce_outbox_str(decoded.get("notification_id"), label="notification_id")
    if event_type == "NotificationDeletedEvent":
        return NotificationDeletedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            notification_id=notification_id,
        )
    type_value = coerce_outbox_str(decoded.get("notification_type"), label="notification_type")
    if type_value not in NOTIFICATION_TYPE_SQL_VALUES:
        raise ValidationError("Notification type is invalid.")
    title = _decode_notification_text(
        decoded.get("title"),
        label="title",
    )
    message = _decode_notification_text(
        decoded.get("message"),
        label="message",
    )
    created_at_ms = coerce_outbox_int(decoded.get("created_at_ms"), label="created_at_ms")
    source = coerce_outbox_optional_str(decoded.get("source"), label="source")
    link_value = decoded.get("link")
    if link_value is None:
        link = None
    else:
        if not isinstance(link_value, dict):
            raise ValidationError("link must be a JSON object.")
        try:
            link = NotificationLink.model_validate(link_value).model_dump(mode="json")
        except pydantic.ValidationError as exception:
            raise ValidationError("link payload shape is invalid.") from exception
    if event_type == "NotificationCreatedEvent":
        return NotificationCreatedEvent(
            event_id=event_id,
            timestamp=timestamp,
            user_id=int(user_id),
            notification_id=notification_id,
            notification_type=type_value,
            title=title,
            message=message,
            created_at_ms=int(created_at_ms),
            source=source,
            link=link,
        )
    raise ValidationError(f"Unsupported outbox event_type: {event_type}")
