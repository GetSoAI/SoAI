"""SoAI - Notification template negotiation for released WebUI clients [backend/core/notifications/notification_transport.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.notifications.notification_contracts import NotificationTemplateId
from core.notifications.notification_record_models import NotificationRecord
from core.notifications.notification_text_models import (
    NotificationTextPlain,
    NotificationTextTemplate,
    notification_text_from_plain,
)
from core.types.json import JSONValue

__all__ = ("project_notification_record", "project_notification_text")


def project_notification_text(
    text: NotificationTextPlain | NotificationTextTemplate,
    accepted_templates: str | None,
) -> NotificationTextPlain | NotificationTextTemplate:
    if isinstance(text, NotificationTextPlain):
        return text
    supported = frozenset((accepted_templates or "").split(","))
    if text.template.value in supported:
        return text
    if text.template == NotificationTemplateId.PLUGIN_BACKEND_UPDATE_TITLE:
        return notification_text_from_plain("Backend update available")
    if text.template == NotificationTemplateId.PLUGIN_BACKEND_UPDATE_MESSAGE:
        return notification_text_from_plain(
            f"A backend update is available for {text.params['pluginName']}. Open Plugins to review it."
        )
    return text


def project_notification_record(
    record: NotificationRecord, accepted_templates: str | None
) -> NotificationRecord:
    updates: dict[str, JSONValue] = {
        "title": project_notification_text(record.title, accepted_templates).model_dump(
            mode="json"
        ),
        "message": project_notification_text(record.message, accepted_templates).model_dump(
            mode="json"
        ),
    }
    payload = record.model_dump(mode="json")
    payload.update(updates)
    return NotificationRecord.model_validate(payload)
