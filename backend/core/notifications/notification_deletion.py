"""SoAI - Shared non-critical notification deletion [backend/core/notifications/notification_deletion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.elicitation_interactions import extract_notification_id
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.types.json import JSONValue

__all__ = (
    "delete_metadata_notification_noncritical",
    "delete_notification_noncritical",
)


async def delete_notification_noncritical(
    *,
    logger: LoggerProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    user_id: int,
    notification_id: str,
    operation: str,
    message: str,
    level: str,
    details: Mapping[str, JSONValue],
) -> None:
    normalized_notification_id = notification_id.strip()
    if not normalized_notification_id:
        return
    try:
        await database_notifications.delete_notification(
            int(user_id),
            notification_id=normalized_notification_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=message,
            operation=operation,
            details=dict(details),
            level=level,
        )


async def delete_metadata_notification_noncritical(
    *,
    logger: LoggerProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    user_id: int,
    metadata: Mapping[str, JSONValue],
    operation: str,
    message: str,
    level: str,
    details: Mapping[str, JSONValue],
) -> None:
    notification_id = extract_notification_id(metadata)
    if notification_id is None:
        return
    await delete_notification_noncritical(
        logger=logger,
        database_notifications=database_notifications,
        user_id=int(user_id),
        notification_id=notification_id,
        operation=operation,
        message=message,
        level=level,
        details=details,
    )
