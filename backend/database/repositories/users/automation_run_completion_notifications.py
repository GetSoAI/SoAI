"""SoAI - Automation run completion notification payloads [backend/database/repositories/users/automation_run_completion_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import StateError
from core.notifications.notification_contracts import (
    NotificationLinkType,
    NotificationTemplateId,
    NotificationType,
)
from core.notifications.notification_record_models import NotificationLink
from core.notifications.notification_text_models import (
    NotificationTextTemplate,
    notification_text_from_template,
)

__all__ = (
    "AutomationRunCompletionNotification",
    "build_automation_run_completion_notification",
)


@dataclass(frozen=True, slots=True)
class AutomationRunCompletionNotification:
    notification_type: NotificationType
    title: NotificationTextTemplate
    message: NotificationTextTemplate
    source: str
    link: NotificationLink


def build_automation_run_completion_notification(
    *,
    run_id: str,
    conv_id: str | None,
    automation_title: str | None,
    notification_type: NotificationType,
    status_message: str | None,
) -> AutomationRunCompletionNotification:
    normalized_title = automation_title.strip() if automation_title is not None else ""
    if notification_type is NotificationType.SUCCESS:
        title = notification_text_from_template(NotificationTemplateId.AUTOMATION_COMPLETED_TITLE)
        if normalized_title:
            message = notification_text_from_template(
                NotificationTemplateId.AUTOMATION_COMPLETED_MESSAGE,
                {"automationTitle": normalized_title},
            )
        else:
            message = notification_text_from_template(
                NotificationTemplateId.AUTOMATION_COMPLETED_MESSAGE_GENERIC,
            )
    elif notification_type in {NotificationType.ERROR, NotificationType.WARNING}:
        if status_message is not None and status_message.strip():
            title = notification_text_from_template(NotificationTemplateId.AUTOMATION_FAILED_TITLE)
            normalized_status = status_message.strip()
            if normalized_title:
                message = notification_text_from_template(
                    NotificationTemplateId.AUTOMATION_FAILED_MESSAGE_WITH_STATUS,
                    {
                        "automationTitle": normalized_title,
                        "statusMessage": normalized_status,
                    },
                )
            else:
                message = notification_text_from_template(
                    NotificationTemplateId.AUTOMATION_FAILED_MESSAGE_WITH_STATUS_GENERIC,
                    {"statusMessage": normalized_status},
                )
        else:
            title = notification_text_from_template(NotificationTemplateId.AUTOMATION_FAILED_TITLE)
            if normalized_title:
                message = notification_text_from_template(
                    NotificationTemplateId.AUTOMATION_FAILED_MESSAGE,
                    {"automationTitle": normalized_title},
                )
            else:
                message = notification_text_from_template(
                    NotificationTemplateId.AUTOMATION_FAILED_MESSAGE_GENERIC,
                )
    else:
        raise StateError("Automation completion notification type is invalid.")
    normalized_conv_id = conv_id.strip() if conv_id is not None else ""
    if normalized_conv_id:
        link = NotificationLink(
            link_type=NotificationLinkType.CONVERSATION,
            value=normalized_conv_id,
        )
    else:
        link = NotificationLink(
            link_type=NotificationLinkType.AUTOMATION_RUN,
            value=run_id.strip() or run_id,
        )
    return AutomationRunCompletionNotification(
        notification_type=notification_type,
        title=title,
        message=message,
        source="automation",
        link=link,
    )
