"""SoAI - Shared chat interaction resolution helpers [backend/features/chat/interaction_resolution_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from core.elicitation.notification_cleanup import (
    cleanup_elicitation_notification_noncritical,
)
from core.errors.exceptions import StateError
from core.logging.protocols import LoggerProtocol
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize

if TYPE_CHECKING:
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.tasks.interaction_mutations import ConversationInteractionMutation
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_interaction_resolution_response",
    "cleanup_interaction_notification",
    "finalize_interaction_resolution",
    "resolve_interaction_cleanup_operation",
)

INTERACTION_CANCEL_CLEANUP_OPERATION = "features.chat.interaction_service.cancel_cleanup"
INTERACTION_RESOLVE_CLEANUP_OPERATION = "features.chat.interaction_service.resolve_cleanup"


async def finalize_interaction_resolution(
    *,
    task_registry: TaskRegistryProtocol,
    task_id: str,
    status: TaskStatus,
    result: Mapping[str, JSONValue] | None,
    status_message: str,
    operation: str,
    conv_id: str,
    interaction_mutation: ConversationInteractionMutation | None = None,
    error_code: int | None = None,
    error_message: str | None = None,
) -> Task:
    resolved = await finalize(
        task_registry,
        task_id,
        status,
        result=result,
        error_code=error_code,
        error_message=error_message,
        status_message=status_message,
        interaction_mutation=interaction_mutation,
    )
    if resolved is None:
        raise StateError(
            "Failed to resolve interaction.",
            operation=operation,
            details={"conv_id": conv_id, "task_id": task_id},
        )
    return resolved


def build_interaction_resolution_response(*, task_id: str, status: str) -> JSONDict:
    return {"task_id": task_id, "status": status}


def resolve_interaction_cleanup_operation(*, action: str) -> str:
    if action == "cancel":
        return INTERACTION_CANCEL_CLEANUP_OPERATION
    return INTERACTION_RESOLVE_CLEANUP_OPERATION


async def cleanup_interaction_notification(
    *,
    database_notifications: DatabaseNotificationsProtocol,
    logger: LoggerProtocol,
    operation: str,
    user_id: int,
    metadata: Mapping[str, JSONValue],
    conv_id: str,
    task_id: str,
    interaction_type: str,
) -> None:
    await cleanup_elicitation_notification_noncritical(
        database_notifications=database_notifications,
        logger=logger,
        operation=operation,
        message="Failed to delete interaction notification (non-critical).",
        user_id=user_id,
        metadata=metadata,
        details={
            "conv_id": conv_id,
            "task_id": task_id,
            "interaction_type": interaction_type,
        },
    )
