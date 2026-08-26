"""SoAI - Notification row normalization [backend/database/repositories/users/notifications_row_normalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import pydantic

from core.errors.exceptions import DatabaseError, ValidationError
from core.notifications.notification_contracts import NotificationType
from core.notifications.notification_link_validation import validate_notification_link
from core.notifications.notification_record_models import (
    NotificationLink,
    NotificationRecord,
)
from core.notifications.notification_text_models import (
    NotificationTextPlain,
    NotificationTextTemplate,
    parse_notification_text_db,
)
from core.serialization.json_parsing import parse_json_value
from core.validation.strings import coerce_optional_trimmed_str
from database.core.row_fields import (
    require_row_epoch_ms,
    require_row_non_empty_str,
    require_row_positive_int,
)
from database.repositories.row_formatting import format_row

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("normalize_notification_row",)

OPERATION = "database_notifications.normalize_row"


def _decode_optional_link(link_json: str | None) -> NotificationLink | None:
    if link_json is None:
        return None
    if not link_json:
        return None
    try:
        decoded = parse_json_value(link_json)
    except ValidationError as exception:
        raise DatabaseError(
            "Failed to decode notification link JSON.",
            operation=OPERATION,
        ) from exception
    if not isinstance(decoded, dict):
        raise DatabaseError(
            "Notification link payload must be a JSON object.",
            operation=OPERATION,
        )
    try:
        link = NotificationLink.model_validate(decoded)
    except pydantic.ValidationError as exception:
        raise DatabaseError(
            "Notification link payload shape is invalid.",
            operation=OPERATION,
        ) from exception
    try:
        return validate_notification_link(link.link_type, link.value)
    except ValidationError as exception:
        raise DatabaseError(
            "Notification link payload is invalid.",
            operation=OPERATION,
        ) from exception


def normalize_notification_row(row: SQLiteRowDict | None) -> NotificationRecord | None:
    normalized = format_row(row)
    if normalized is None:
        return None

    def build_error(message: str) -> DatabaseError:
        return DatabaseError(message, operation=OPERATION)

    notification_id_value = require_row_non_empty_str(
        normalized.get("id"),
        label="Notification row contains invalid id value.",
        build_error=build_error,
    )
    user_id_value = require_row_positive_int(
        normalized.get("user_id"),
        label="Notification row contains invalid user_id value.",
        build_error=build_error,
    )
    type_value = require_row_non_empty_str(
        normalized.get("type"),
        label="Notification row contains invalid type value.",
        build_error=build_error,
    )
    title_value = require_row_non_empty_str(
        normalized.get("title"),
        label="Notification row contains invalid title value.",
        build_error=build_error,
    )
    message_value = require_row_non_empty_str(
        normalized.get("message"),
        label="Notification row contains invalid message value.",
        build_error=build_error,
    )
    try:
        title: NotificationTextPlain | NotificationTextTemplate = parse_notification_text_db(
            title_value,
        )
    except ValueError as exception:
        raise DatabaseError(
            "Notification row contains invalid title value.",
            operation=OPERATION,
        ) from exception
    try:
        message: NotificationTextPlain | NotificationTextTemplate = parse_notification_text_db(
            message_value,
        )
    except ValueError as exception:
        raise DatabaseError(
            "Notification row contains invalid message value.",
            operation=OPERATION,
        ) from exception
    source = coerce_optional_trimmed_str(normalized.get("source"))
    link_json_value = normalized.get("link_json")
    if link_json_value is None:
        link_json = None
    elif isinstance(link_json_value, str):
        link_json = link_json_value
    else:
        raise DatabaseError(
            "Notification row contains invalid link_json value.",
            operation=OPERATION,
        )
    created_at_value = require_row_epoch_ms(
        normalized.get("created_at_ms"),
        label="Notification row contains invalid created_at_ms value.",
        build_error=build_error,
    )
    read_at_raw = normalized.get("read_at_ms")
    if read_at_raw is None:
        read_at_value = None
    else:
        read_at_value = require_row_epoch_ms(
            read_at_raw,
            label="Notification row contains invalid read_at_ms value.",
            build_error=build_error,
        )
    try:
        notification_type = NotificationType(type_value)
    except ValueError as exception:
        raise DatabaseError(
            "Notification row contains invalid type value.",
            operation=OPERATION,
        ) from exception
    try:
        return NotificationRecord.model_validate(
            {
                "id": str(notification_id_value),
                "user_id": int(user_id_value),
                "created_at_ms": int(created_at_value),
                "type": notification_type,
                "title": title.model_dump(mode="json"),
                "message": message.model_dump(mode="json"),
                "source": source,
                "link": _decode_optional_link(link_json),
                "read_at_ms": int(read_at_value) if read_at_value is not None else None,
            },
        )
    except pydantic.ValidationError as exception:
        raise DatabaseError(
            "Notification row failed validation.",
            operation=OPERATION,
        ) from exception
