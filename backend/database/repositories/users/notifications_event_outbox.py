"""SoAI - Notification domain event outbox helpers [backend/database/repositories/users/notifications_event_outbox.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pydantic

from core.errors.exceptions import StateError, ValidationError
from core.events.domain_event_payload import build_domain_event_payload
from core.notifications.notification_contracts import NOTIFICATION_TYPE_SQL_VALUES
from core.notifications.notification_record_models import NotificationLink
from core.notifications.notification_text_models import parse_notification_text_db
from core.serialization.json_parsing import parse_json_value
from core.validation.integers import is_strict_int
from database.repositories.event_outbox.sync_ops import sync_enqueue_domain_event_payload

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "sync_enqueue_notification_created_domain_event",
    "sync_enqueue_notification_deleted_domain_event",
    "sync_enqueue_notifications_cleared_domain_event",
    "sync_enqueue_notifications_marked_read_domain_event",
)


def _require_non_empty_notification_text(value: str, *, label: str) -> str:
    if not isinstance(value, str):
        raise StateError(f"Notification outbox {label} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise StateError(f"Notification outbox {label} must be a non-empty string.")
    return normalized


def _require_notification_outbox_user_id(value: int) -> int:
    if not is_strict_int(value):
        raise StateError("Notification outbox user_id must be an integer.")
    return int(value)


def _decode_optional_link_payload(value: str | None) -> dict[str, JSONValue] | None:
    if value is None:
        return None
    normalized_value = value.strip()
    if not normalized_value:
        return None
    try:
        decoded = parse_json_value(normalized_value)
    except ValidationError as exception:
        raise StateError("Notification outbox link_json is invalid JSON.") from exception
    if not isinstance(decoded, dict):
        raise StateError("Notification outbox link_json must be a JSON object.")
    try:
        link = NotificationLink.model_validate(decoded)
    except pydantic.ValidationError as exception:
        raise StateError("Notification outbox link_json payload shape is invalid.") from exception
    return link.model_dump(mode="json")


def sync_enqueue_notification_created_domain_event(
    conn: sqlite3.Connection,
    *,
    created_at_ms: int,
    user_id: int,
    notification_id: str,
    notification_type: str,
    title: str,
    message: str,
    source: str | None,
    link_json: str | None,
) -> None:
    if not is_strict_int(created_at_ms):
        raise StateError("Notification outbox created_at_ms must be an integer.")
    normalized_user_id = _require_notification_outbox_user_id(user_id)
    normalized_notification_id = _require_non_empty_notification_text(
        notification_id,
        label="notification_id",
    )
    normalized_notification_type = _require_non_empty_notification_text(
        notification_type,
        label="notification_type",
    )
    if normalized_notification_type not in NOTIFICATION_TYPE_SQL_VALUES:
        raise StateError("Notification outbox notification_type is invalid.")
    try:
        title_payload: JSONValue = parse_notification_text_db(title).model_dump(mode="json")
    except ValueError as exception:
        raise StateError("Notification outbox title is invalid.") from exception
    try:
        message_payload: JSONValue = parse_notification_text_db(message).model_dump(mode="json")
    except ValueError as exception:
        raise StateError("Notification outbox message is invalid.") from exception
    payload = build_domain_event_payload(
        fields={
            "user_id": normalized_user_id,
            "notification_id": normalized_notification_id,
            "notification_type": normalized_notification_type,
            "title": title_payload,
            "message": message_payload,
            "created_at_ms": int(created_at_ms),
        },
    )
    if source is not None:
        if not isinstance(source, str):
            raise StateError("Notification outbox source must be a string.")
        normalized_source = source.strip()
        if normalized_source:
            payload["source"] = normalized_source
    link = _decode_optional_link_payload(link_json)
    if link is not None:
        payload["link"] = link
    sync_enqueue_domain_event_payload(
        conn,
        event_type="NotificationCreatedEvent",
        payload=payload,
        created_at_ms=created_at_ms,
    )


def sync_enqueue_notification_deleted_domain_event(
    conn: sqlite3.Connection,
    *,
    created_at_ms: int,
    user_id: int,
    notification_id: str,
) -> None:
    normalized_user_id = _require_notification_outbox_user_id(user_id)
    payload = build_domain_event_payload(
        fields={
            "user_id": normalized_user_id,
            "notification_id": _require_non_empty_notification_text(
                notification_id,
                label="notification_id",
            ),
        },
    )
    sync_enqueue_domain_event_payload(
        conn,
        event_type="NotificationDeletedEvent",
        payload=payload,
        created_at_ms=created_at_ms,
    )


def sync_enqueue_notifications_cleared_domain_event(
    conn: sqlite3.Connection,
    *,
    created_at_ms: int,
    user_id: int,
) -> None:
    normalized_user_id = _require_notification_outbox_user_id(user_id)
    payload = build_domain_event_payload(
        fields={
            "user_id": normalized_user_id,
        },
    )
    sync_enqueue_domain_event_payload(
        conn,
        event_type="NotificationsClearedEvent",
        payload=payload,
        created_at_ms=created_at_ms,
    )


def sync_enqueue_notifications_marked_read_domain_event(
    conn: sqlite3.Connection,
    *,
    created_at_ms: int,
    user_id: int,
    notification_ids: list[str],
) -> None:
    normalized_user_id = _require_notification_outbox_user_id(user_id)
    normalized_notification_ids: list[str] = []
    for notification_id in notification_ids:
        if not isinstance(notification_id, str):
            raise StateError("Notification outbox notification_ids must contain strings.")
        normalized_notification_id = _require_non_empty_notification_text(
            notification_id,
            label="notification_ids entry",
        )
        if normalized_notification_id not in normalized_notification_ids:
            normalized_notification_ids.append(normalized_notification_id)
    if not normalized_notification_ids:
        raise StateError("Notification outbox notification_ids must be a non-empty list.")
    payload = build_domain_event_payload(
        fields={
            "user_id": normalized_user_id,
        },
    )
    payload["notification_ids"] = normalized_notification_ids
    sync_enqueue_domain_event_payload(
        conn,
        event_type="NotificationsMarkedReadEvent",
        payload=payload,
        created_at_ms=created_at_ms,
    )
