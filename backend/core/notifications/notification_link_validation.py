"""SoAI - Notification link validation [backend/core/notifications/notification_link_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit

from core.errors.exceptions import ValidationError
from core.notifications.notification_contracts import NotificationLinkType
from core.notifications.notification_record_models import NotificationLink

__all__ = ("validate_notification_link",)


def validate_notification_link(link_type: NotificationLinkType, value: str) -> NotificationLink:
    normalized_value = str(value or "").strip()
    if not normalized_value:
        raise ValidationError("Notification link value is invalid.")
    if link_type == NotificationLinkType.URL:
        return NotificationLink(
            link_type=link_type,
            value=_validate_notification_url_or_route(normalized_value),
        )
    return NotificationLink(link_type=link_type, value=normalized_value)


def _validate_notification_url_or_route(value: str) -> str:
    if any(character.isspace() for character in value):
        raise ValidationError("Notification link must not include whitespace.")
    parsed = urlsplit(value)
    if parsed.scheme in {"http", "https"}:
        return _validate_absolute_notification_url(parsed, value)
    if parsed.scheme or parsed.netloc or value.startswith("//") or "\\" in value:
        raise ValidationError(
            "Notification URL must be absolute http/https or an internal relative route.",
        )
    return value


def _validate_absolute_notification_url(parsed: SplitResult, value: str) -> str:
    if not parsed.netloc or not parsed.hostname:
        raise ValidationError("Notification URL must be absolute and include a host.")
    if parsed.username is not None or parsed.password is not None:
        raise ValidationError("Notification URL must not include credentials.")
    return value
