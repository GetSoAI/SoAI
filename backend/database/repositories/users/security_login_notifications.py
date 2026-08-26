"""SoAI - Security login notification sync operations [backend/database/repositories/users/security_login_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
import sqlite3

from core.notifications.notification_contracts import (
    SECURITY_LOGIN_NOTIFICATION_SOURCE,
    NotificationTemplateId,
    NotificationType,
)
from database.repositories.users.notification_admin_alerts import (
    sync_create_template_admin_alert_if_due,
)

__all__ = ("sync_create_login_throttle_admin_alert_if_due",)

LOGIN_THROTTLE_ALERT_ID = "security.login.throttle"
MS_PER_MINUTE = 60_000


def sync_create_login_throttle_admin_alert_if_due(
    conn: sqlite3.Connection,
    now_ms: int,
    cooldown_ms: int,
    max_per_user: int,
) -> int:
    window_minutes = max(1, int(math.ceil(float(cooldown_ms) / float(MS_PER_MINUTE))))
    return sync_create_template_admin_alert_if_due(
        conn,
        LOGIN_THROTTLE_ALERT_ID,
        NotificationType.WARNING.value,
        NotificationTemplateId.SECURITY_LOGIN_THROTTLE_TITLE.value,
        {},
        NotificationTemplateId.SECURITY_LOGIN_THROTTLE_MESSAGE.value,
        {"windowMinutes": str(window_minutes)},
        "attemptCount",
        SECURITY_LOGIN_NOTIFICATION_SOURCE,
        int(now_ms),
        int(cooldown_ms),
        int(max_per_user),
    )
