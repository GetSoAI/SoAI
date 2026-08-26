"""SoAI - MCP ask_user task lifecycle and completion decoding [backend/mcp/tools/ask_user_task_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.elicitation_ask_user import (
    ASK_USER_INTERACTION_TYPE,
    build_ask_user_task_metadata,
)
from core.notifications.notification_contracts import NotificationTemplateId
from core.tasks.enums import TaskStatus
from core.users.user_id import is_strict_user_id
from mcp.tools.ask_user_answers import require_answers_payload
from mcp.tools.elicitation_task_notifications import (
    create_elicitation_task_with_notification,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.tasks.task import Task
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "OPERATION",
    "OPERATION_NOTIFICATION_CLEANUP",
    "build_ask_user_task_metadata",
    "create_ask_user_task",
    "decode_ask_user_task_completion",
)

OPERATION = "mcp.tools.ask_user.wait_for_completion"
OPERATION_NOTIFICATION_CLEANUP = "mcp.tools.ask_user.notification_cleanup"


async def create_ask_user_task(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
    conv_id: str,
    questions: list[JSONDict],
) -> Task:
    resolved_conv_id = str(conv_id or "").strip()
    if not resolved_conv_id:
        raise MCPToolError(-32602, "ask_user requires a conversation id.")
    if not is_strict_user_id(user_id):
        raise MCPToolError(-32602, "ask_user requires a valid user id.")
    resolved_user_id = int(user_id)
    metadata = build_ask_user_task_metadata(questions)
    return await create_elicitation_task_with_notification(
        utility_tools,
        user_id=resolved_user_id,
        conv_id=resolved_conv_id,
        interaction_type=ASK_USER_INTERACTION_TYPE,
        suspension_phase="awaiting_ask_user_result",
        metadata=metadata,
        title_template=NotificationTemplateId.ASK_USER_REQUIRED_TITLE,
        message_template=NotificationTemplateId.ASK_USER_REQUIRED_MESSAGE,
        failure_message="Failed to create a notification for ask_user.",
        failure_status_message="Failed",
    )


def decode_ask_user_task_completion(completed_task: Task | None) -> JSONDict:
    if completed_task is None:
        raise MCPToolError(-32603, f"{ASK_USER_INTERACTION_TYPE} task not found.")
    if completed_task.status == TaskStatus.COMPLETED:
        return require_answers_payload(completed_task.result)
    if completed_task.status == TaskStatus.CANCELLED:
        message = (
            completed_task.error_message or f"{ASK_USER_INTERACTION_TYPE} was cancelled by the user"
        )
        raise MCPToolError(-32603, message)
    if completed_task.status == TaskStatus.FAILED:
        message = completed_task.error_message or f"{ASK_USER_INTERACTION_TYPE} task failed"
        raise MCPToolError(-32603, message)
    raise MCPToolError(
        -32603,
        f"{ASK_USER_INTERACTION_TYPE} task ended with unexpected status: {completed_task.status.value}",
    )
