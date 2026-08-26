"""SoAI - Notification creation payload normalization [backend/database/repositories/users/notifications_creation_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from dataclasses import dataclass

from core.errors.exceptions import DatabaseError, ValidationError
from core.notifications.notification_link_validation import validate_notification_link
from core.notifications.notification_record_models import NotificationLink
from core.notifications.notification_text_models import (
    NotificationTextPlain,
    NotificationTextTemplate,
    serialize_notification_text_db,
)
from core.serialization.json import serialize_json_compact_stable_strict
from core.validation.strings import coerce_optional_trimmed_str
from database.repositories.users.notifications_value_validation import (
    normalize_notification_text_payload,
)

__all__ = ("NotificationCreatePayload", "build_notification_create_payload")

OPERATION_SERIALIZE_LINK = "database_notifications.serialize_link"


@dataclass(frozen=True, slots=True)
class NotificationCreatePayload:
    notification_id: str
    title: str
    message: str
    source: str | None
    link_json: str | None


def build_notification_create_payload(
    *,
    title: NotificationTextPlain | NotificationTextTemplate,
    message: NotificationTextPlain | NotificationTextTemplate,
    source: str | None,
    link: NotificationLink | None,
    notification_id: str | None,
) -> NotificationCreatePayload:
    title_db = serialize_notification_text_db(
        normalize_notification_text_payload(title, label="title"),
    )
    message_db = serialize_notification_text_db(
        normalize_notification_text_payload(message, label="message"),
    )
    normalized_source = coerce_optional_trimmed_str(source)
    if link is None:
        link_json = None
    else:
        normalized_link = validate_notification_link(link.link_type, link.value)
        try:
            link_json = serialize_json_compact_stable_strict(
                normalized_link.model_dump(mode="json"),
            )
        except (TypeError, ValueError) as exception:
            raise DatabaseError(
                "Failed to serialize notification link.",
                operation=OPERATION_SERIALIZE_LINK,
            ) from exception
    if notification_id is None:
        resolved_notification_id = f"notif_{uuid.uuid4().hex}"
    else:
        resolved_notification_id = str(notification_id).strip()
        if not resolved_notification_id:
            raise ValidationError("notification_id is invalid.")
    return NotificationCreatePayload(
        notification_id=resolved_notification_id,
        title=str(title_db),
        message=str(message_db),
        source=normalized_source,
        link_json=link_json,
    )
