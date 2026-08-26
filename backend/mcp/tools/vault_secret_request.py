"""SoAI - MCP utility tool: vault_secret_request [backend/mcp/tools/vault_secret_request.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from mcp.tools.argument_fields import (
    optional_string,
    reject_unexpected_parameters,
    require_non_empty_string,
)
from mcp.tools.elicitation_task_lifecycle import (
    wait_for_elicitation_task_completion,
)
from mcp.tools.error import MCPToolError, get_arg
from mcp.tools.openai_owner_context import require_openai_conversation_owner
from mcp.tools.vault_secret_request_models import decode_vault_secret_request_task_completion
from mcp.tools.vault_secret_request_task_lifecycle import (
    OPERATION,
    OPERATION_NOTIFICATION_CLEANUP,
    create_vault_secret_request_task,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("tool_vault_secret_request",)

LOGGER_NAME = "SoAI.mcp.tools.vault_secret_request"
_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "current_page_url",
        "title",
        "message",
        "allow_save_to_vault",
    },
)


async def tool_vault_secret_request(
    utility_tools: MCPUtilityToolsProtocol,
    arguments: JSONDict,
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)
    reject_unexpected_parameters(arguments, _ALLOWED_KEYS)
    owner_key = utility_tools.runtime_sessions.current_owner_key()
    user_id, conv_id = require_openai_conversation_owner(
        owner_key, tool_name="vault_secret_request"
    )
    current_page_url = require_non_empty_string(
        get_arg(arguments, "current_page_url"),
        key="current_page_url",
    )
    title = optional_string(arguments.get("title"), key="title") or "Credentials"
    message = (
        optional_string(arguments.get("message"), key="message") or "Enter credentials to continue."
    )
    allow_save_to_vault_raw = arguments.get("allow_save_to_vault")
    allow_save_to_vault = True
    if allow_save_to_vault_raw is not None:
        if not isinstance(allow_save_to_vault_raw, bool):
            raise MCPToolError(-32602, "allow_save_to_vault must be a boolean when provided.")
        allow_save_to_vault = bool(allow_save_to_vault_raw)
    task = await create_vault_secret_request_task(
        utility_tools,
        user_id=user_id,
        conv_id=conv_id,
        current_page_url=current_page_url,
        title=title,
        message=message,
        allow_save_to_vault=allow_save_to_vault,
        save_label_default=None,
    )
    completed_task = await wait_for_elicitation_task_completion(
        utility_tools,
        interaction_type="vault_secret_request",
        operation=OPERATION,
        operation_notification_cleanup=OPERATION_NOTIFICATION_CLEANUP,
        task_id=task.task_id,
        conv_id=conv_id,
        expires_at_ms=task.ttl_expires_at_ms,
        logger=logger,
    )
    return await decode_vault_secret_request_task_completion(utility_tools, completed_task)
