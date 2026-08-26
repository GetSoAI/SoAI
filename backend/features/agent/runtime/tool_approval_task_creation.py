"""SoAI - Tool approval task creation and notification emission [backend/features/agent/runtime/tool_approval_task_creation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.notifications.conversation_attention_delivery import (
    deliver_conversation_attention_notification,
)
from core.notifications.notification_contracts import (
    NotificationLinkType,
    NotificationTemplateId,
)
from core.notifications.notification_record_models import NotificationLink
from core.notifications.notification_text_models import notification_text_from_template
from core.tasks.creation import create
from core.tasks.enums import TaskStatus
from core.tasks.errors import TaskIDCollisionError
from core.tasks.noncritical_finalization import finalize_noncritical
from core.tasks.type_catalog import TASK_TYPE_MCP_ELICITATION
from core.tool_approval.constants import TOOL_APPROVAL_INTERACTION_TYPE
from core.tool_approval.task_metadata import (
    require_tool_approval_notification_id,
    require_tool_approval_tool_name,
)

if TYPE_CHECKING:
    from core.database.task_requests import ConversationInteractionCheckpointRequest
    from core.logging.protocols import LoggerProtocol
    from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.tasks.protocols_registry import TaskRegistryProtocol
    from core.tasks.task import Task
    from core.types.json import JSONDict

__all__ = (
    "build_tool_approval_notification_id",
    "build_tool_approval_task_id",
    "ensure_tool_approval_task",
)

OPERATION_TASK_COLLISION = "agent.tool_approval_task_creation.task_collision"
OPERATION_NOTIFICATION_CREATE_FAILED = (
    "agent.tool_approval_task_creation.notification_create_failed"
)


def build_tool_approval_task_id(
    *,
    conv_id: str,
    turn_id: str,
    iteration_index: int,
    tool_call_id: str,
) -> str:
    seed = f"{conv_id}:{turn_id}:{int(iteration_index)}:{tool_call_id}".encode()
    digest = hashlib.sha256(seed).hexdigest()[:20]
    return f"tool_approval_{digest}"


def build_tool_approval_notification_id(*, task_id: str) -> str:
    digest = hashlib.sha256(f"{task_id}:notification".encode()).hexdigest()[:24]
    return f"notif_{digest}"


async def ensure_tool_approval_task(
    task_registry: TaskRegistryProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    conversation_attention: ConversationAttentionCoordinatorProtocol,
    logger: LoggerProtocol,
    *,
    task_id: str,
    user_id: int,
    conv_id: str,
    task_cancellation_id: str,
    metadata: JSONDict,
    interaction_checkpoint: ConversationInteractionCheckpointRequest | None,
    user_interaction_timeout_ms: int,
) -> Task:
    try:
        task = await create(
            task_registry,
            task_type=TASK_TYPE_MCP_ELICITATION,
            user_id=user_id,
            owner_id=conv_id,
            owner_type="conversation",
            task_id=task_id,
            cancellation_id=task_cancellation_id,
            status=TaskStatus.INPUT_REQUIRED,
            status_message="Awaiting user tool approval",
            poll_interval_ms=750,
            progress_total=100,
            metadata=metadata,
            interaction_checkpoint=interaction_checkpoint,
            ttl_ms=user_interaction_timeout_ms,
        )
        notification_id = require_tool_approval_notification_id(metadata)
        tool_name = require_tool_approval_tool_name(metadata)
        try:
            await deliver_conversation_attention_notification(
                attention=conversation_attention,
                task_registry=task_registry,
                database_notifications=database_notifications,
                user_id=int(user_id),
                conversation_id=conv_id,
                interaction_type=TOOL_APPROVAL_INTERACTION_TYPE,
                task_id=task.task_id,
                notification_id=notification_id,
                title=notification_text_from_template(
                    NotificationTemplateId.TOOL_APPROVAL_REQUIRED_TITLE,
                ),
                message=notification_text_from_template(
                    NotificationTemplateId.TOOL_APPROVAL_REQUIRED_MESSAGE,
                    {"toolName": tool_name},
                ),
                source="agent",
                link=NotificationLink(
                    link_type=NotificationLinkType.CONVERSATION,
                    value=str(conv_id).strip() or str(conv_id),
                ),
            )
        except asyncio.CancelledError:
            await finalize_noncritical(
                task_registry,
                task.task_id,
                TaskStatus.CANCELLED,
                error_message="Tool approval notification creation cancelled.",
                status_message="Cancelled",
                logger=logger,
                operation="agent.tool_approval_task_creation.notification_create_cancelled",
                log_message="Failed to finalize tool approval task after notification cancellation (non-critical).",
                details={"task_id": task.task_id, "conv_id": conv_id, "user_id": int(user_id)},
            )
            raise
        except RECOVERABLE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_NOTIFICATION_CREATE_FAILED,
            )
            log_exception(
                logger,
                coerced,
                message="Failed to create tool approval notification; cancelling approval task.",
                operation=OPERATION_NOTIFICATION_CREATE_FAILED,
                level="warning",
                details={"task_id": task_id, "conv_id": conv_id, "user_id": int(user_id)},
            )
            await finalize_noncritical(
                task_registry,
                task.task_id,
                TaskStatus.FAILED,
                error_message="Tool approval notification creation failed.",
                status_message="Failed",
                logger=logger,
                operation="agent.tool_approval_task_creation.notification_create_failed.finalize",
                log_message="Failed to finalize tool approval task after notification creation failure (non-critical).",
                details={"task_id": task.task_id, "conv_id": conv_id, "user_id": int(user_id)},
            )
            raise coerced from exception
        return task
    except TaskIDCollisionError as exception:
        existing = await task_registry.get(task_id)
        if existing is None:
            raise StateError(
                "Tool approval task already exists but could not be retrieved.",
                operation=OPERATION_TASK_COLLISION,
                details={"task_id": task_id},
            ) from exception
        require_tool_approval_notification_id(existing.metadata)
        require_tool_approval_tool_name(existing.metadata)
        return existing
