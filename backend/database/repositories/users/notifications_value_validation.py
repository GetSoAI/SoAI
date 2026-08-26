"""SoAI - User notification repository value validation [backend/database/repositories/users/notifications_value_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.clamped_numeric import read_config_nonnegative_int
from core.errors.exceptions import ValidationError
from core.notifications.notification_text_models import (
    NotificationTextPlain,
    NotificationTextTemplate,
    notification_text_from_plain,
)
from core.users.user_id import is_strict_user_id
from core.validation.integers import is_strict_int
from core.validation.record_fields import require_int, require_optional_int

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.types.json import JSONValue

__all__ = (
    "coerce_notification_count",
    "normalize_notification_cursor_created_at",
    "normalize_notification_text_payload",
    "read_max_notifications_per_user",
    "require_notification_list_limit",
    "require_notification_user_id",
)


def read_max_notifications_per_user(config: ConfigProtocol) -> int:
    max_per_user = read_config_nonnegative_int(
        config,
        "SERVER.WEBUI.NOTIFICATIONS.MAX_PER_USER",
        1000,
    )
    return max(int(max_per_user) or 1, 1)


def coerce_notification_count(value: JSONValue | None) -> int:
    if is_strict_int(value):
        return max(value, 0)
    return 0


def normalize_notification_text_payload(
    value: NotificationTextPlain | NotificationTextTemplate,
    *,
    label: str,
) -> NotificationTextPlain | NotificationTextTemplate:
    if isinstance(value, NotificationTextPlain):
        return notification_text_from_plain(value.text)
    if isinstance(value, NotificationTextTemplate):
        return value
    raise ValidationError(f"{label} payload is invalid.")


def require_notification_user_id(user_id: int) -> int:
    if not is_strict_user_id(user_id):
        raise ValidationError("user_id is invalid.")
    return int(user_id)


def require_notification_list_limit(limit: int) -> int:
    return require_int(
        limit,
        label="limit",
        build_error=ValidationError,
        minimum=1,
        invalid_message="limit must be a positive integer.",
    )


def normalize_notification_cursor_created_at(value: int | None) -> int | None:
    return require_optional_int(
        value,
        label="before_created_at_ms",
        build_error=ValidationError,
        invalid_message="before_created_at_ms must be an integer.",
    )
