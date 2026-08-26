"""SoAI - External account notification links [backend/features/external_accounts/notification_links.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.notifications.notification_contracts import NotificationLinkType
from core.notifications.notification_link_validation import validate_notification_link
from core.notifications.notification_record_models import NotificationLink

__all__ = ("build_external_accounts_settings_link",)

_EXTERNAL_ACCOUNTS_SETTINGS_ROUTE = "settings?tab=webui-external-accounts"


def build_external_accounts_settings_link() -> NotificationLink:
    return validate_notification_link(
        NotificationLinkType.URL,
        _EXTERNAL_ACCOUNTS_SETTINGS_ROUTE,
    )
