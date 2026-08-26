"""SoAI - Elicitation notification cleanup helpers [backend/core/elicitation/notification_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.elicitation_interactions import extract_notification_id
from core.notifications.notification_deletion import (
    delete_metadata_notification_noncritical,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = ("cleanup_elicitation_notification_noncritical",)


async def cleanup_elicitation_notification_noncritical(
    *,
    database_notifications: DatabaseNotificationsProtocol,
    logger: LoggerProtocol,
    user_id: int,
    metadata: Mapping[str, JSONValue],
    operation: str,
    message: str,
    details: Mapping[str, JSONValue] | None = None,
) -> None:
    notification_id = extract_notification_id(metadata)
    if notification_id is None:
        return
    if int(user_id) <= 0:
        return
    resolved_details: JSONDict = dict(details) if isinstance(details, Mapping) else {}
    if "notification_id" not in resolved_details:
        resolved_details["notification_id"] = notification_id
    if "user_id" not in resolved_details:
        resolved_details["user_id"] = int(user_id)
    await delete_metadata_notification_noncritical(
        logger=logger,
        database_notifications=database_notifications,
        user_id=int(user_id),
        metadata=dict(metadata),
        operation=operation,
        message=message,
        level="warning",
        details=resolved_details,
    )
