"""SoAI - MCP vault_secret_request task lifecycle [backend/mcp/tools/vault_secret_request_task_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.elicitation_vault_secret_request import (
    CREDENTIAL_REQUEST_INTERACTION_TYPE,
    build_vault_secret_request_task_metadata,
)
from core.notifications.notification_contracts import NotificationTemplateId
from core.users.user_id import is_strict_user_id
from mcp.tools.elicitation_task_notifications import (
    create_elicitation_task_with_notification,
)
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.tasks.task import Task
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = (
    "OPERATION",
    "OPERATION_NOTIFICATION_CLEANUP",
    "create_vault_secret_request_task",
)

OPERATION = "mcp.tools.vault_secret_request.wait_for_completion"
OPERATION_NOTIFICATION_CLEANUP = "mcp.tools.vault_secret_request.notification_cleanup"


async def create_vault_secret_request_task(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
    conv_id: str,
    current_page_url: str,
    title: str,
    message: str,
    allow_save_to_vault: bool,
    save_label_default: str | None = None,
) -> Task:
    resolved_conv_id = str(conv_id or "").strip()
    if not resolved_conv_id:
        raise MCPToolError(-32602, "vault_secret_request requires a conversation id.")
    if not is_strict_user_id(user_id):
        raise MCPToolError(-32602, "vault_secret_request requires a valid user id.")
    resolved_user_id = int(user_id)
    try:
        metadata = build_vault_secret_request_task_metadata(
            current_page_url=current_page_url,
            title=title,
            message=message,
            allow_save_to_vault=allow_save_to_vault,
            save_label_default=save_label_default,
        )
    except ValueError as exception:
        raise MCPToolError(-32602, str(exception)) from exception
    return await create_elicitation_task_with_notification(
        utility_tools,
        user_id=resolved_user_id,
        conv_id=resolved_conv_id,
        interaction_type=CREDENTIAL_REQUEST_INTERACTION_TYPE,
        suspension_phase="awaiting_vault_secret",
        metadata=metadata,
        title_template=NotificationTemplateId.CREDENTIAL_REQUEST_REQUIRED_TITLE,
        message_template=NotificationTemplateId.CREDENTIAL_REQUEST_REQUIRED_MESSAGE,
        failure_message="Failed to create a notification for vault_secret_request.",
        failure_status_message="Failed",
    )
