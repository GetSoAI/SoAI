"""SoAI - Shared MCP elicitation task creation with notifications [backend/mcp/tools/elicitation_task_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from core.config.user_interaction_timeout import resolve_user_interaction_timeout_ms
from core.conversations.interaction_checkpoint import (
    raise_if_conversation_input_suspended,
)
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
from core.tasks.enums import TaskStatus
from core.tasks.finalization import finalize
from mcp.tools.elicitation_task_creation import (
    build_mcp_elicitation_task_id,
    ensure_mcp_elicitation_task,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("create_elicitation_task_with_notification",)


async def create_elicitation_task_with_notification(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
    conv_id: str,
    interaction_type: str,
    suspension_phase: str,
    metadata: JSONDict,
    title_template: NotificationTemplateId,
    message_template: NotificationTemplateId,
    failure_message: str,
    failure_status_message: str,
) -> Task:
    request_context = utility_tools.active_request_context.get()
    if request_context is None:
        raise MCPToolError(-32603, "Conversation interaction context is unavailable.")
    user_interaction_timeout_ms = resolve_user_interaction_timeout_ms(utility_tools.config)
    task_id = build_mcp_elicitation_task_id(
        utility_tools,
        conv_id=conv_id,
        interaction_type=interaction_type,
    )
    notification_id = f"notif_{hashlib.sha256(f'{task_id}:notification'.encode()).hexdigest()[:24]}"
    metadata["notification_id"] = notification_id
    task = await ensure_mcp_elicitation_task(
        utility_tools,
        user_id=int(user_id),
        conv_id=conv_id,
        interaction_type=interaction_type,
        suspension_phase=suspension_phase,
        metadata=metadata,
        user_interaction_timeout_ms=user_interaction_timeout_ms,
    )
    try:
        await deliver_conversation_attention_notification(
            attention=utility_tools.conversation_attention,
            task_registry=utility_tools.task_registry,
            database_notifications=utility_tools.database_notifications,
            user_id=int(user_id),
            conversation_id=conv_id,
            interaction_type=interaction_type,
            task_id=task.task_id,
            notification_id=notification_id,
            title=notification_text_from_template(title_template),
            message=notification_text_from_template(message_template),
            source="agent",
            link=NotificationLink(link_type=NotificationLinkType.CONVERSATION, value=conv_id),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        await finalize(
            utility_tools.task_registry,
            task.task_id,
            TaskStatus.FAILED,
            error_code=-32603,
            error_message=failure_message,
            status_message=failure_status_message,
        )
        raise MCPToolError(-32603, failure_message) from exception
    await raise_if_conversation_input_suspended(
        utility_tools.task_registry,
        input_id=request_context.conversation_input_id,
        task_id=task.task_id,
    )
    return task
