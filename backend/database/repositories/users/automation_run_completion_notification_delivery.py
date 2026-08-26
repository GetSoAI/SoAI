"""SoAI - Automation run completion notification delivery [backend/database/repositories/users/automation_run_completion_notification_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from database.repositories.users.automation_run_completion_notifications import (
    build_automation_run_completion_notification,
)

if TYPE_CHECKING:
    from core.notifications.notification_contracts import NotificationType
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.types.json import JSONDict

__all__ = (
    "emit_automation_run_completion_notification",
    "emit_automation_run_completion_notification_if_enabled",
)

LOGGER_NAME = "SoAI.database.repositories.automation_run_completion_notification_delivery"
OPERATION_AUTOMATION_RUN_NOTIFICATION = "database.automation_runs.completion_notification"


async def emit_automation_run_completion_notification(
    database_notifications: DatabaseNotificationsProtocol,
    run_record: JSONDict,
    *,
    run_id: str,
    user_id: int,
    notification_type: NotificationType,
    status_message: str | None,
) -> None:
    notification = build_automation_run_completion_notification(
        run_id=run_id,
        conv_id=str(run_record["conv_id"]) if isinstance(run_record.get("conv_id"), str) else None,
        automation_title=(
            str(run_record["title"]) if isinstance(run_record.get("title"), str) else None
        ),
        notification_type=notification_type,
        status_message=status_message,
    )
    await database_notifications.create_notification(
        int(user_id),
        notification.notification_type,
        notification.title,
        notification.message,
        source=notification.source,
        link=notification.link,
    )


async def emit_automation_run_completion_notification_if_enabled(
    database_notifications: DatabaseNotificationsProtocol,
    run_record: JSONDict | None,
    *,
    emit_notifications: bool,
    run_id: str,
    user_id: int,
    notification_type: NotificationType,
    status_message: str | None,
) -> None:
    if not emit_notifications or not isinstance(run_record, dict):
        return
    logger = get_logger(LOGGER_NAME)
    try:
        await emit_automation_run_completion_notification(
            database_notifications,
            run_record,
            run_id=run_id,
            user_id=user_id,
            notification_type=notification_type,
            status_message=status_message,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_AUTOMATION_RUN_NOTIFICATION,
            details={"run_id": run_id, "user_id": int(user_id)},
        )
        log_exception(
            logger,
            coerced,
            message="Failed to emit automation completion notification after run state commit.",
            operation=OPERATION_AUTOMATION_RUN_NOTIFICATION,
            level="warning",
            details={"run_id": run_id, "user_id": int(user_id)},
        )
